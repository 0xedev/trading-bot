"""
Technical Analysis Engine - Inspired by TradeBridge
Provides technical indicators and signal generation capabilities
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime

try:
    import pandas_ta as ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logging.warning("pandas-ta not available. Install with: pip install pandas-ta")

# Import or create TradingSignal class
try:
    from src.signal_engine import TradingSignal
except ImportError:
    # Fallback: create a simple TradingSignal class
    class TradingSignal:
        def __init__(self, action: str, confidence: float, reason: str = "",
                     price: float = 0, symbol: str = "", metadata: dict = None,
                     **kwargs):
            self.action = action
            self.confidence = confidence
            self.reason = reason
            self.price = price
            self.symbol = symbol
            self.timestamp = datetime.now()
            self.metadata = metadata or {}

logger = logging.getLogger(__name__)


class TechnicalAnalysisEngine:
    """
    Technical Analysis Engine for generating trading signals from price data.
    Inspired by TradeBridge's comprehensive technical analysis capabilities.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the technical analysis engine.
        
        Args:
            config: Configuration dictionary for indicators and thresholds
        """
        self.config = config or self._get_default_config()
        
        if not TA_AVAILABLE:
            logger.warning("Technical analysis features limited without pandas-ta")
    
    def _get_default_config(self) -> Dict:
        """Get default configuration for technical analysis"""
        return {
            'sma_short': 20,
            'sma_long': 50,
            'ema_period': 12,
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'bb_period': 20,
            'bb_std': 2,
            'atr_period': 14,
            'volume_ma_period': 20
        }
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate multiple technical indicators on price data.
        
        Args:
            df: DataFrame with OHLCV data (open, high, low, close, volume)
            
        Returns:
            DataFrame with added indicator columns
        """
        if not TA_AVAILABLE:
            logger.warning("Cannot calculate indicators without pandas-ta")
            return df
        
        try:
            # Moving Averages
            df['sma_20'] = ta.sma(df['close'], length=self.config['sma_short'])
            df['sma_50'] = ta.sma(df['close'], length=self.config['sma_long'])
            df['ema_12'] = ta.ema(df['close'], length=self.config['ema_period'])
            
            # RSI (Relative Strength Index)
            df['rsi'] = ta.rsi(df['close'], length=self.config['rsi_period'])
            
            # MACD (Moving Average Convergence Divergence)
            macd = ta.macd(
                df['close'],
                fast=self.config['macd_fast'],
                slow=self.config['macd_slow'],
                signal=self.config['macd_signal']
            )
            if macd is not None:
                df = pd.concat([df, macd], axis=1)
            
            # Bollinger Bands
            bbands = ta.bbands(df['close'], length=self.config['bb_period'], std=self.config['bb_std'])
            if bbands is not None:
                df = pd.concat([df, bbands], axis=1)
            
            # ATR (Average True Range) for volatility
            df['atr'] = ta.atr(
                df['high'],
                df['low'],
                df['close'],
                length=self.config['atr_period']
            )
            
            # Stochastic Oscillator
            stoch = ta.stoch(df['high'], df['low'], df['close'])
            if stoch is not None:
                df = pd.concat([df, stoch], axis=1)
            
            # Volume indicators
            df['volume_sma'] = ta.sma(df['volume'], length=self.config['volume_ma_period'])
            
            # OBV (On-Balance Volume)
            df['obv'] = ta.obv(df['close'], df['volume'])
            
            logger.info(f"Calculated {len(df.columns)} indicators")
            return df
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signals(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> List[TradingSignal]:
        """
        Generate trading signals from technical indicators.
        
        Args:
            df: DataFrame with calculated indicators
            symbol: Trading symbol
            
        Returns:
            List of TradingSignal objects
        """
        if len(df) < 2:
            logger.warning("Insufficient data for signal generation")
            return []
        
        signals = []
        
        try:
            # Get latest values
            latest = df.iloc[-1]
            previous = df.iloc[-2]
            
            # RSI Signals
            rsi_signal = self._check_rsi_signal(latest, previous)
            if rsi_signal:
                signals.append(rsi_signal)
            
            # MACD Signals
            macd_signal = self._check_macd_signal(latest, previous)
            if macd_signal:
                signals.append(macd_signal)
            
            # Moving Average Crossover
            ma_signal = self._check_ma_crossover(latest, previous)
            if ma_signal:
                signals.append(ma_signal)
            
            # Bollinger Bands
            bb_signal = self._check_bollinger_bands(latest)
            if bb_signal:
                signals.append(bb_signal)
            
            # Volume Breakout
            volume_signal = self._check_volume_breakout(latest)
            if volume_signal:
                signals.append(volume_signal)
            
            # Add symbol to all signals
            for signal in signals:
                signal.symbol = symbol
                signal.timestamp = datetime.now()
            
            logger.info(f"Generated {len(signals)} technical signals for {symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            return []
    
    def _check_rsi_signal(self, latest: pd.Series, previous: pd.Series) -> Optional[TradingSignal]:
        """Check for RSI-based signals"""
        if 'rsi' not in latest or pd.isna(latest['rsi']):
            return None
        
        rsi = latest['rsi']
        
        # Oversold condition - potential buy
        if rsi < self.config['rsi_oversold']:
            # Confidence increases linearly from 0.65 to 0.9 as RSI goes from 30 to 0
            # Ensures confidence stays in [0.65, 0.9] range naturally
            oversold_degree = (self.config['rsi_oversold'] - rsi) / self.config['rsi_oversold']
            confidence = 0.65 + (0.25 * oversold_degree)  # Range: 0.65 to 0.9
            return TradingSignal(
                action='BUY',
                confidence=confidence,
                reason=f'RSI Oversold ({rsi:.1f})',
                price=latest['close'],
                metadata={'indicator': 'RSI', 'value': rsi}
            )
        
        # Overbought condition - potential sell
        elif rsi > self.config['rsi_overbought']:
            # Confidence increases linearly from 0.65 to 0.9 as RSI goes from 70 to 100
            overbought_degree = (rsi - self.config['rsi_overbought']) / (100 - self.config['rsi_overbought'])
            confidence = 0.65 + (0.25 * overbought_degree)  # Range: 0.65 to 0.9
            return TradingSignal(
                action='SELL',
                confidence=confidence,
                reason=f'RSI Overbought ({rsi:.1f})',
                price=latest['close'],
                metadata={'indicator': 'RSI', 'value': rsi}
            )
        
        return None
    
    def _check_macd_signal(self, latest: pd.Series, previous: pd.Series) -> Optional[TradingSignal]:
        """Check for MACD crossover signals"""
        macd_col = f'MACD_{self.config["macd_fast"]}_{self.config["macd_slow"]}_{self.config["macd_signal"]}'
        signal_col = f'MACDs_{self.config["macd_fast"]}_{self.config["macd_slow"]}_{self.config["macd_signal"]}'
        
        if macd_col not in latest or signal_col not in latest:
            return None
        
        if pd.isna(latest[macd_col]) or pd.isna(latest[signal_col]):
            return None
        
        macd_current = latest[macd_col]
        signal_current = latest[signal_col]
        macd_prev = previous[macd_col]
        signal_prev = previous[signal_col]
        
        # Bullish crossover
        if macd_prev <= signal_prev and macd_current > signal_current:
            return TradingSignal(
                action='BUY',
                confidence=0.75,
                reason='MACD Bullish Crossover',
                price=latest['close'],
                metadata={'indicator': 'MACD', 'macd': macd_current, 'signal': signal_current}
            )
        
        # Bearish crossover
        elif macd_prev >= signal_prev and macd_current < signal_current:
            return TradingSignal(
                action='SELL',
                confidence=0.75,
                reason='MACD Bearish Crossover',
                price=latest['close'],
                metadata={'indicator': 'MACD', 'macd': macd_current, 'signal': signal_current}
            )
        
        return None
    
    def _check_ma_crossover(self, latest: pd.Series, previous: pd.Series) -> Optional[TradingSignal]:
        """Check for moving average crossover signals"""
        if 'sma_20' not in latest or 'sma_50' not in latest:
            return None
        
        if pd.isna(latest['sma_20']) or pd.isna(latest['sma_50']):
            return None
        
        sma20_current = latest['sma_20']
        sma50_current = latest['sma_50']
        sma20_prev = previous['sma_20']
        sma50_prev = previous['sma_50']
        
        # Golden Cross (bullish)
        if sma20_prev <= sma50_prev and sma20_current > sma50_current:
            return TradingSignal(
                action='BUY',
                confidence=0.8,
                reason='Golden Cross (SMA 20/50)',
                price=latest['close'],
                metadata={'indicator': 'MA_CROSS', 'sma20': sma20_current, 'sma50': sma50_current}
            )
        
        # Death Cross (bearish)
        elif sma20_prev >= sma50_prev and sma20_current < sma50_current:
            return TradingSignal(
                action='SELL',
                confidence=0.8,
                reason='Death Cross (SMA 20/50)',
                price=latest['close'],
                metadata={'indicator': 'MA_CROSS', 'sma20': sma20_current, 'sma50': sma50_current}
            )
        
        return None
    
    def _check_bollinger_bands(self, latest: pd.Series) -> Optional[TradingSignal]:
        """Check for Bollinger Band signals"""
        bb_lower = f'BBL_{self.config["bb_period"]}_{self.config["bb_std"]}.0'
        bb_upper = f'BBU_{self.config["bb_period"]}_{self.config["bb_std"]}.0'
        
        if bb_lower not in latest or bb_upper not in latest:
            return None
        
        if pd.isna(latest[bb_lower]) or pd.isna(latest[bb_upper]):
            return None
        
        price = latest['close']
        lower_band = latest[bb_lower]
        upper_band = latest[bb_upper]
        
        # Price touching lower band - potential buy
        if price <= lower_band:
            return TradingSignal(
                action='BUY',
                confidence=0.7,
                reason='Price at Bollinger Lower Band',
                price=price,
                metadata={'indicator': 'BBANDS', 'lower': lower_band, 'upper': upper_band}
            )
        
        # Price touching upper band - potential sell
        elif price >= upper_band:
            return TradingSignal(
                action='SELL',
                confidence=0.7,
                reason='Price at Bollinger Upper Band',
                price=price,
                metadata={'indicator': 'BBANDS', 'lower': lower_band, 'upper': upper_band}
            )
        
        return None
    
    def _check_volume_breakout(self, latest: pd.Series) -> Optional[TradingSignal]:
        """Check for volume breakout signals"""
        if 'volume' not in latest or 'volume_sma' not in latest:
            return None
        
        if pd.isna(latest['volume']) or pd.isna(latest['volume_sma']):
            return None
        
        volume = latest['volume']
        volume_sma = latest['volume_sma']
        
        # High volume breakout (1.5x average volume)
        if volume > volume_sma * 1.5:
            return TradingSignal(
                action='BUY',
                confidence=0.65,
                reason=f'Volume Breakout ({volume/volume_sma:.1f}x avg)',
                price=latest['close'],
                metadata={'indicator': 'VOLUME', 'volume': volume, 'volume_sma': volume_sma}
            )
        
        return None
    
    def get_market_summary(self, df: pd.DataFrame) -> Dict:
        """
        Get a summary of current market conditions based on indicators.
        
        Args:
            df: DataFrame with calculated indicators
            
        Returns:
            Dictionary with market summary
        """
        if len(df) == 0:
            return {}
        
        latest = df.iloc[-1]
        summary = {
            'price': latest.get('close', 0),
            'timestamp': datetime.now().isoformat()
        }
        
        # RSI condition
        if 'rsi' in latest and not pd.isna(latest['rsi']):
            rsi = latest['rsi']
            summary['rsi'] = rsi
            if rsi < 30:
                summary['rsi_condition'] = 'Oversold'
            elif rsi > 70:
                summary['rsi_condition'] = 'Overbought'
            else:
                summary['rsi_condition'] = 'Neutral'
        
        # Trend (based on moving averages)
        if 'sma_20' in latest and 'sma_50' in latest:
            if not pd.isna(latest['sma_20']) and not pd.isna(latest['sma_50']):
                if latest['sma_20'] > latest['sma_50']:
                    summary['trend'] = 'Bullish'
                else:
                    summary['trend'] = 'Bearish'
        
        # Volatility (based on ATR)
        if 'atr' in latest and not pd.isna(latest['atr']):
            atr = latest['atr']
            atr_percent = (atr / latest['close']) * 100
            summary['atr'] = atr
            summary['volatility'] = 'High' if atr_percent > 3 else 'Normal'
        
        return summary


def get_sample_data(symbol: str = "BTCUSDT", periods: int = 100, seed: Optional[int] = 42) -> pd.DataFrame:
    """
    Generate sample OHLCV data for testing (when real data is not available).
    
    Args:
        symbol: Trading symbol
        periods: Number of periods to generate
        seed: Random seed for reproducibility (None for random data)
        
    Returns:
        DataFrame with sample OHLCV data
    """
    if seed is not None:
        np.random.seed(seed)
    
    # Generate random walk for price
    base_price = 50000 if 'BTC' in symbol else 2500
    returns = np.random.randn(periods) * 0.02
    prices = base_price * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame({
        'timestamp': pd.date_range(start='2024-01-01', periods=periods, freq='1h'),
        'open': prices,
        'high': prices * (1 + np.abs(np.random.randn(periods) * 0.01)),
        'low': prices * (1 - np.abs(np.random.randn(periods) * 0.01)),
        'close': prices * (1 + np.random.randn(periods) * 0.005),
        'volume': np.random.uniform(100, 1000, periods)
    })
    
    return df


if __name__ == "__main__":
    # Test the technical analysis engine
    logging.basicConfig(level=logging.INFO)
    
    print("Technical Analysis Engine Test")
    print("=" * 50)
    
    # Create engine
    engine = TechnicalAnalysisEngine()
    
    # Get sample data
    df = get_sample_data("BTCUSDT", periods=100)
    print(f"\nGenerated {len(df)} periods of sample data")
    
    # Calculate indicators
    df = engine.calculate_indicators(df)
    print(f"Calculated indicators: {list(df.columns)}")
    
    # Generate signals
    signals = engine.generate_signals(df, symbol="BTCUSDT")
    print(f"\nGenerated {len(signals)} signals:")
    for signal in signals:
        print(f"  - {signal.action}: {signal.reason} (confidence: {signal.confidence:.2f})")
    
    # Get market summary
    summary = engine.get_market_summary(df)
    print(f"\nMarket Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
