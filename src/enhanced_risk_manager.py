"""
Enhanced Risk Manager - Inspired by TradeBridge
Implements institutional-grade risk management with Kelly Criterion, VaR, and circuit breakers
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)


class TradeRecord:
    """Record of a single trade for performance tracking"""
    
    def __init__(self, timestamp: datetime, symbol: str, action: str, 
                 entry_price: float, quantity: float, pnl: float = 0):
        self.timestamp = timestamp
        self.symbol = symbol
        self.action = action
        self.entry_price = entry_price
        self.quantity = quantity
        self.pnl = pnl
        self.exit_price = None
        self.exit_time = None
        self.is_win = None


class EnhancedRiskManager:
    """
    Institutional-grade risk management system.
    Features: Kelly Criterion, VaR, circuit breakers, drawdown tracking, performance metrics.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the enhanced risk manager.
        
        Args:
            config: Configuration dictionary for risk parameters
        """
        self.config = config or self._get_default_config()
        
        # Trade history
        self.trade_history: List[TradeRecord] = []
        self.daily_pnl: deque = deque(maxlen=30)  # Last 30 days
        self.current_positions: Dict[str, float] = {}
        
        # Risk state
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.trading_paused = False
        self.pause_until = None
        self.daily_loss = 0
        self.peak_portfolio_value = self.config['initial_capital']
        
        logger.info("Enhanced Risk Manager initialized")
    
    def _get_default_config(self) -> Dict:
        """Get default risk management configuration"""
        return {
            'initial_capital': 100000,
            'risk_tolerance': 0.02,  # 2% risk per trade
            'max_position_size': 0.1,  # 10% max position
            'max_daily_loss': 0.05,  # 5% max daily loss
            'max_drawdown': 0.20,  # 20% max drawdown
            'max_consecutive_losses': 3,
            'circuit_breaker_pause_hours': 1,
            'kelly_fraction': 0.25,  # Fractional Kelly for safety
            'var_confidence': 0.95,  # 95% VaR confidence
            'min_trade_confidence': 0.65,  # Minimum confidence to trade
            'max_correlation': 0.7,  # Max correlation between positions
            'volatility_adjustment': True,
            'atr_multiplier': 2.0,  # Stop loss ATR multiplier
        }
    
    def kelly_position_size(self, win_rate: Optional[float] = None,
                           avg_win: Optional[float] = None,
                           avg_loss: Optional[float] = None,
                           signal_confidence: float = 0.7) -> float:
        """
        Calculate Kelly Criterion position size.
        
        Args:
            win_rate: Historical win rate (uses signal confidence if None)
            avg_win: Average winning trade return
            avg_loss: Average losing trade return
            signal_confidence: Confidence of current signal
            
        Returns:
            Position size as percentage of portfolio (0.0 to 1.0)
        """
        # Use historical data if available
        if win_rate is None or avg_win is None or avg_loss is None:
            win_rate, avg_win, avg_loss = self._calculate_historical_stats()
        
        # If we don't have enough history, use signal confidence
        if win_rate == 0 or avg_loss == 0:
            win_rate = signal_confidence
            avg_win = 0.05  # Assume 5% avg win
            avg_loss = 0.03  # Assume 3% avg loss
        
        # Kelly formula: f = (p*W - (1-p)*L) / W
        # where p = win rate, W = avg win, L = avg loss
        kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        
        # Apply fractional Kelly for safety
        fractional_kelly = kelly * self.config['kelly_fraction']
        
        # Bound between 0 and max position size
        position_size = max(0, min(fractional_kelly, self.config['max_position_size']))
        
        logger.debug(f"Kelly sizing: win_rate={win_rate:.2f}, kelly={kelly:.3f}, "
                    f"fractional={fractional_kelly:.3f}, final={position_size:.3f}")
        
        return position_size
    
    def _calculate_historical_stats(self) -> Tuple[float, float, float]:
        """Calculate win rate and average win/loss from trade history"""
        if len(self.trade_history) < 5:
            return 0, 0, 0
        
        wins = [t for t in self.trade_history if t.is_win]
        losses = [t for t in self.trade_history if t.is_win == False]
        
        win_rate = len(wins) / len(self.trade_history) if self.trade_history else 0
        avg_win = np.mean([t.pnl for t in wins]) if wins else 0
        avg_loss = abs(np.mean([t.pnl for t in losses])) if losses else 0
        
        return win_rate, avg_win, avg_loss
    
    def calculate_var(self, returns: Optional[np.array] = None,
                     confidence: Optional[float] = None) -> float:
        """
        Calculate Value at Risk (VaR).
        
        Args:
            returns: Array of historical returns (uses trade history if None)
            confidence: Confidence level (uses config if None)
            
        Returns:
            VaR value (expected maximum loss at confidence level)
        """
        if confidence is None:
            confidence = self.config['var_confidence']
        
        if returns is None:
            if len(self.trade_history) < 10:
                return 0
            returns = np.array([t.pnl for t in self.trade_history])
        
        var = np.percentile(returns, (1 - confidence) * 100)
        
        logger.debug(f"VaR at {confidence*100}% confidence: {var:.2f}")
        return var
    
    def check_circuit_breakers(self, portfolio_value: float) -> Tuple[bool, str]:
        """
        Check if any circuit breakers should halt trading.
        
        Args:
            portfolio_value: Current portfolio value
            
        Returns:
            Tuple of (can_trade, reason)
        """
        # Check if already paused
        if self.trading_paused:
            if self.pause_until and datetime.now() < self.pause_until:
                remaining = (self.pause_until - datetime.now()).seconds / 60
                return False, f"Trading paused for {remaining:.0f} more minutes"
            else:
                # Resume trading
                self.trading_paused = False
                self.pause_until = None
                logger.info("Circuit breaker reset - resuming trading")
        
        # Check consecutive losses
        if self.consecutive_losses >= self.config['max_consecutive_losses']:
            self._trigger_circuit_breaker("Consecutive losses limit reached")
            return False, f"{self.consecutive_losses} consecutive losses"
        
        # Check daily loss limit
        max_daily_loss_amount = portfolio_value * self.config['max_daily_loss']
        if self.daily_loss < -max_daily_loss_amount:
            self._trigger_circuit_breaker("Daily loss limit exceeded")
            return False, f"Daily loss: ${abs(self.daily_loss):.2f}"
        
        # Check max drawdown
        current_drawdown = (self.peak_portfolio_value - portfolio_value) / self.peak_portfolio_value
        if current_drawdown > self.config['max_drawdown']:
            self._trigger_circuit_breaker("Maximum drawdown exceeded")
            return False, f"Drawdown: {current_drawdown*100:.1f}%"
        
        # Update peak if new high
        if portfolio_value > self.peak_portfolio_value:
            self.peak_portfolio_value = portfolio_value
        
        return True, "All checks passed"
    
    def _trigger_circuit_breaker(self, reason: str):
        """Trigger circuit breaker to pause trading"""
        self.trading_paused = True
        self.pause_until = datetime.now() + timedelta(hours=self.config['circuit_breaker_pause_hours'])
        logger.warning(f"🚨 CIRCUIT BREAKER TRIGGERED: {reason}")
        logger.warning(f"Trading paused until {self.pause_until.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def calculate_position_size(self, signal, portfolio_value: float,
                               atr: Optional[float] = None) -> float:
        """
        Calculate optimal position size using multiple methods.
        
        Args:
            signal: Trading signal object
            portfolio_value: Current portfolio value
            atr: Average True Range for volatility adjustment
            
        Returns:
            Position size as percentage of portfolio
        """
        # Check minimum confidence
        if signal.confidence < self.config['min_trade_confidence']:
            logger.debug(f"Signal confidence {signal.confidence:.2f} below minimum "
                        f"{self.config['min_trade_confidence']:.2f}")
            return 0
        
        # Kelly Criterion position size
        kelly_size = self.kelly_position_size(signal_confidence=signal.confidence)
        
        # Confidence-based adjustment
        confidence_size = signal.confidence * self.config['max_position_size']
        
        # Volatility adjustment using ATR
        if atr and self.config['volatility_adjustment']:
            # Higher volatility = smaller position
            volatility_factor = 1.0 / (1.0 + atr / 100)
            volatility_size = confidence_size * volatility_factor
        else:
            volatility_size = confidence_size
        
        # Take the minimum of all methods for conservative sizing
        position_size = min(kelly_size, confidence_size, volatility_size)
        
        # Final safety cap
        position_size = min(position_size, self.config['max_position_size'])
        
        logger.info(f"Position sizing: kelly={kelly_size:.3f}, confidence={confidence_size:.3f}, "
                   f"volatility={volatility_size:.3f}, final={position_size:.3f}")
        
        return position_size
    
    def calculate_stop_loss(self, entry_price: float, action: str,
                           atr: Optional[float] = None) -> float:
        """
        Calculate stop loss price using ATR or fixed percentage.
        
        Args:
            entry_price: Entry price for the position
            action: 'BUY' or 'SELL'
            atr: Average True Range
            
        Returns:
            Stop loss price
        """
        if atr:
            # ATR-based stop loss
            stop_distance = atr * self.config['atr_multiplier']
        else:
            # Fixed percentage stop loss (3%)
            stop_distance = entry_price * 0.03
        
        if action == 'BUY':
            stop_loss = entry_price - stop_distance
        else:  # SELL
            stop_loss = entry_price + stop_distance
        
        logger.debug(f"Stop loss for {action} at ${entry_price:.2f}: ${stop_loss:.2f}")
        return stop_loss
    
    def record_trade(self, symbol: str, action: str, entry_price: float,
                    quantity: float, pnl: float = 0):
        """Record a trade for performance tracking"""
        trade = TradeRecord(
            timestamp=datetime.now(),
            symbol=symbol,
            action=action,
            entry_price=entry_price,
            quantity=quantity,
            pnl=pnl
        )
        self.trade_history.append(trade)
        
        # Update consecutive wins/losses
        if pnl > 0:
            trade.is_win = True
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        elif pnl < 0:
            trade.is_win = False
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        
        # Update daily loss
        self.daily_loss += pnl
        
        logger.info(f"Trade recorded: {action} {symbol} @ ${entry_price:.2f}, "
                   f"P&L: ${pnl:.2f}, Consecutive: W{self.consecutive_wins}/L{self.consecutive_losses}")
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sharpe Ratio from trade history.
        
        Args:
            risk_free_rate: Annual risk-free rate (default 2%)
            
        Returns:
            Sharpe Ratio
        """
        if len(self.trade_history) < 10:
            return 0
        
        returns = np.array([t.pnl for t in self.trade_history])
        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
        
        if np.std(excess_returns) == 0:
            return 0
        
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
        return sharpe
    
    def calculate_sortino_ratio(self, risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sortino Ratio (like Sharpe but only considers downside volatility).
        
        Args:
            risk_free_rate: Annual risk-free rate
            
        Returns:
            Sortino Ratio
        """
        if len(self.trade_history) < 10:
            return 0
        
        returns = np.array([t.pnl for t in self.trade_history])
        excess_returns = returns - (risk_free_rate / 252)
        
        # Only consider negative returns for downside deviation
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0 or np.std(downside_returns) == 0:
            return 0
        
        sortino = np.mean(excess_returns) / np.std(downside_returns) * np.sqrt(252)
        return sortino
    
    def get_risk_metrics(self, portfolio_value: float) -> Dict:
        """
        Get comprehensive risk metrics.
        
        Args:
            portfolio_value: Current portfolio value
            
        Returns:
            Dictionary of risk metrics
        """
        metrics = {
            'portfolio_value': portfolio_value,
            'peak_value': self.peak_portfolio_value,
            'daily_pnl': self.daily_loss,
            'consecutive_wins': self.consecutive_wins,
            'consecutive_losses': self.consecutive_losses,
            'trading_paused': self.trading_paused,
            'total_trades': len(self.trade_history)
        }
        
        # Calculate drawdown
        if self.peak_portfolio_value > 0:
            metrics['drawdown'] = (self.peak_portfolio_value - portfolio_value) / self.peak_portfolio_value
        else:
            metrics['drawdown'] = 0
        
        # Win rate
        if self.trade_history:
            wins = sum(1 for t in self.trade_history if t.is_win)
            metrics['win_rate'] = wins / len(self.trade_history)
        else:
            metrics['win_rate'] = 0
        
        # Sharpe and Sortino ratios
        metrics['sharpe_ratio'] = self.calculate_sharpe_ratio()
        metrics['sortino_ratio'] = self.calculate_sortino_ratio()
        
        # VaR
        if len(self.trade_history) >= 10:
            returns = np.array([t.pnl for t in self.trade_history])
            metrics['var_95'] = self.calculate_var(returns, confidence=0.95)
        else:
            metrics['var_95'] = 0
        
        # Average win/loss
        wins = [t.pnl for t in self.trade_history if t.is_win]
        losses = [t.pnl for t in self.trade_history if t.is_win == False]
        metrics['avg_win'] = np.mean(wins) if wins else 0
        metrics['avg_loss'] = np.mean(losses) if losses else 0
        
        # Profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        metrics['profit_factor'] = total_wins / total_losses if total_losses > 0 else 0
        
        return metrics
    
    def reset_daily_metrics(self):
        """Reset daily metrics (call at start of each trading day)"""
        self.daily_loss = 0
        logger.info("Daily risk metrics reset")
    
    def can_open_position(self, symbol: str, portfolio_value: float) -> Tuple[bool, str]:
        """
        Check if we can open a new position.
        
        Args:
            symbol: Trading symbol
            portfolio_value: Current portfolio value
            
        Returns:
            Tuple of (can_open, reason)
        """
        # Check circuit breakers
        can_trade, reason = self.check_circuit_breakers(portfolio_value)
        if not can_trade:
            return False, reason
        
        # Check if we already have a position in this symbol
        if symbol in self.current_positions:
            return False, f"Already have position in {symbol}"
        
        # Check portfolio concentration (max % of portfolio in single position)
        position_count = len(self.current_positions)
        if position_count >= 10:  # Max 10 concurrent positions
            return False, "Maximum concurrent positions reached"
        
        return True, "Position approved"


if __name__ == "__main__":
    # Test the enhanced risk manager
    logging.basicConfig(level=logging.INFO)
    
    print("Enhanced Risk Manager Test")
    print("=" * 50)
    
    # Create risk manager
    risk_mgr = EnhancedRiskManager()
    
    # Test Kelly position sizing
    kelly_size = risk_mgr.kelly_position_size(
        win_rate=0.6,
        avg_win=0.05,
        avg_loss=0.03,
        signal_confidence=0.75
    )
    print(f"\nKelly position size: {kelly_size:.3f} ({kelly_size*100:.1f}%)")
    
    # Test circuit breakers
    can_trade, reason = risk_mgr.check_circuit_breakers(portfolio_value=100000)
    print(f"\nCircuit breaker check: {can_trade} - {reason}")
    
    # Simulate some trades
    print("\nSimulating trades...")
    for i in range(5):
        pnl = np.random.randn() * 500  # Random P&L
        risk_mgr.record_trade(
            symbol="BTCUSDT",
            action="BUY",
            entry_price=50000,
            quantity=0.1,
            pnl=pnl
        )
    
    # Get risk metrics
    metrics = risk_mgr.get_risk_metrics(portfolio_value=101500)
    print(f"\nRisk Metrics:")
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.3f}")
        else:
            print(f"  {key}: {value}")
