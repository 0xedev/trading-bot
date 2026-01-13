# Integration Guide: TradeBridge Features into Trading-Bot

This guide shows how to integrate the newly added TradeBridge-inspired features into the trading bot.

## New Modules Added

### 1. Technical Analysis Engine (`src/technical_analysis.py`)

Provides comprehensive technical analysis capabilities:
- 100+ technical indicators (via pandas-ta)
- Signal generation from RSI, MACD, Moving Averages, Bollinger Bands
- Volume analysis and breakout detection
- Market condition summary

**Key Features:**
- RSI-based oversold/overbought detection
- MACD crossover signals
- Golden/Death cross (SMA 20/50)
- Bollinger Band mean reversion
- Volume breakout identification

### 2. Enhanced Risk Manager (`src/enhanced_risk_manager.py`)

Institutional-grade risk management:
- Kelly Criterion position sizing
- Value at Risk (VaR) calculation
- Circuit breakers (consecutive losses, daily loss limits, max drawdown)
- Performance metrics (Sharpe Ratio, Sortino Ratio, Win Rate)
- ATR-based stop loss calculation

**Key Features:**
- Automatic trading pause on risk threshold breach
- Adaptive position sizing based on historical performance
- Comprehensive risk metrics tracking
- Trade history and performance analytics

## Quick Start

### Basic Usage

```python
from technical_analysis import TechnicalAnalysisEngine
from enhanced_risk_manager import EnhancedRiskManager
import pandas as pd

# Initialize engines
tech_engine = TechnicalAnalysisEngine()
risk_mgr = EnhancedRiskManager()

# Get price data (OHLCV format)
df = pd.DataFrame({
    'open': [...],
    'high': [...],
    'low': [...],
    'close': [...],
    'volume': [...]
})

# Calculate technical indicators
df = tech_engine.calculate_indicators(df)

# Generate technical signals
tech_signals = tech_engine.generate_signals(df, symbol="BTCUSDT")

# For each signal, calculate position size with risk management
for signal in tech_signals:
    # Check if we can trade
    can_trade, reason = risk_mgr.check_circuit_breakers(portfolio_value=100000)
    
    if can_trade:
        # Calculate optimal position size
        position_size = risk_mgr.calculate_position_size(
            signal=signal,
            portfolio_value=100000,
            atr=df['atr'].iloc[-1] if 'atr' in df.columns else None
        )
        
        # Calculate stop loss
        stop_loss = risk_mgr.calculate_stop_loss(
            entry_price=signal.price,
            action=signal.action,
            atr=df['atr'].iloc[-1] if 'atr' in df.columns else None
        )
        
        print(f"Signal: {signal.action} {signal.symbol}")
        print(f"Position Size: {position_size*100:.1f}%")
        print(f"Stop Loss: ${stop_loss:.2f}")
```

## Integration with Existing Trading Bot

### Step 1: Combine PDF Signals with Technical Signals

```python
from src.main import TradingBotOrchestrator
from src.technical_analysis import TechnicalAnalysisEngine
from src.nlp_processing import extract_trading_signals

# Initialize components
bot = TradingBotOrchestrator()
tech_engine = TechnicalAnalysisEngine()

# Get PDF-based signals (existing functionality)
pdf_texts = bot.extract_pdfs()
nlp_analysis = analyze_sentiment(pdf_texts)
pdf_signals = extract_trading_signals(nlp_analysis)

# Get technical signals (new functionality)
price_data = get_historical_data("BTCUSDT")  # You need to implement this
tech_signals = tech_engine.generate_signals(price_data, "BTCUSDT")

# Combine signals with conviction scoring
combined_signals = combine_signal_sources(
    pdf_signals=pdf_signals,
    technical_signals=tech_signals,
    weights={'pdf': 0.4, 'technical': 0.6}
)
```

### Step 2: Multi-Strategy Conviction Scoring

```python
def combine_signal_sources(pdf_signals, technical_signals, weights):
    """
    Combine signals from multiple sources with weighted conviction.
    """
    signal_dict = {}
    
    # Aggregate PDF signals
    for signal in pdf_signals:
        symbol = signal.symbol
        if symbol not in signal_dict:
            signal_dict[symbol] = {'buy': 0, 'sell': 0, 'signals': []}
        
        weighted_conf = signal.confidence * weights['pdf']
        if signal.action.upper() == 'BUY':
            signal_dict[symbol]['buy'] += weighted_conf
        elif signal.action.upper() == 'SELL':
            signal_dict[symbol]['sell'] += weighted_conf
        signal_dict[symbol]['signals'].append(('PDF', signal))
    
    # Aggregate technical signals
    for signal in technical_signals:
        symbol = signal.symbol
        if symbol not in signal_dict:
            signal_dict[symbol] = {'buy': 0, 'sell': 0, 'signals': []}
        
        weighted_conf = signal.confidence * weights['technical']
        if signal.action.upper() == 'BUY':
            signal_dict[symbol]['buy'] += weighted_conf
        elif signal.action.upper() == 'SELL':
            signal_dict[symbol]['sell'] += weighted_conf
        signal_dict[symbol]['signals'].append(('Technical', signal))
    
    # Generate consensus signals
    consensus_signals = []
    for symbol, data in signal_dict.items():
        if data['buy'] > data['sell'] and data['buy'] > 0.6:
            # Strong buy signal
            consensus_signals.append({
                'symbol': symbol,
                'action': 'BUY',
                'confidence': data['buy'],
                'sources': data['signals']
            })
        elif data['sell'] > data['buy'] and data['sell'] > 0.6:
            # Strong sell signal
            consensus_signals.append({
                'symbol': symbol,
                'action': 'SELL',
                'confidence': data['sell'],
                'sources': data['signals']
            })
    
    return consensus_signals
```

### Step 3: Enhanced Risk Management Integration

```python
from src.enhanced_risk_manager import EnhancedRiskManager

# Initialize risk manager
risk_mgr = EnhancedRiskManager({
    'initial_capital': 100000,
    'risk_tolerance': 0.02,
    'max_position_size': 0.10,
    'max_daily_loss': 0.05,
    'max_drawdown': 0.20,
    'max_consecutive_losses': 3,
    'kelly_fraction': 0.25
})

# Before executing trades
portfolio_value = get_current_portfolio_value()

# Check circuit breakers
can_trade, reason = risk_mgr.check_circuit_breakers(portfolio_value)
if not can_trade:
    logger.warning(f"Trading halted: {reason}")
    exit()

# For each signal
for signal in consensus_signals:
    # Check if we can open this position
    can_open, reason = risk_mgr.can_open_position(signal['symbol'], portfolio_value)
    
    if can_open:
        # Calculate position size using Kelly Criterion
        position_size = risk_mgr.calculate_position_size(
            signal=signal,
            portfolio_value=portfolio_value,
            atr=get_atr(signal['symbol'])  # From technical analysis
        )
        
        # Calculate stop loss
        entry_price = get_current_price(signal['symbol'])
        stop_loss = risk_mgr.calculate_stop_loss(
            entry_price=entry_price,
            action=signal['action'],
            atr=get_atr(signal['symbol'])
        )
        
        # Execute trade with risk controls
        execute_trade_with_risk_controls(
            symbol=signal['symbol'],
            action=signal['action'],
            position_size=position_size,
            stop_loss=stop_loss
        )
        
        # Record trade
        risk_mgr.record_trade(
            symbol=signal['symbol'],
            action=signal['action'],
            entry_price=entry_price,
            quantity=position_size * portfolio_value / entry_price
        )
```

## Advanced Features

### Real-time Monitoring Dashboard

```python
# Get comprehensive risk metrics
metrics = risk_mgr.get_risk_metrics(portfolio_value=portfolio_value)

print("\n📊 Risk Metrics Dashboard")
print("=" * 50)
print(f"Portfolio Value: ${metrics['portfolio_value']:,.2f}")
print(f"Peak Value: ${metrics['peak_value']:,.2f}")
print(f"Drawdown: {metrics['drawdown']*100:.2f}%")
print(f"Daily P&L: ${metrics['daily_pnl']:,.2f}")
print(f"\n📈 Performance")
print(f"Win Rate: {metrics['win_rate']*100:.1f}%")
print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"Sortino Ratio: {metrics['sortino_ratio']:.2f}")
print(f"Profit Factor: {metrics['profit_factor']:.2f}")
print(f"\n⚡ Current State")
print(f"Consecutive Wins: {metrics['consecutive_wins']}")
print(f"Consecutive Losses: {metrics['consecutive_losses']}")
print(f"Trading Status: {'⏸️  PAUSED' if metrics['trading_paused'] else '▶️  ACTIVE'}")
```

### Market Analysis Summary

```python
# Get market condition summary
summary = tech_engine.get_market_summary(price_data)

print("\n📊 Market Analysis")
print("=" * 50)
print(f"Price: ${summary['price']:,.2f}")
print(f"RSI: {summary.get('rsi', 'N/A')} ({summary.get('rsi_condition', 'N/A')})")
print(f"Trend: {summary.get('trend', 'N/A')}")
print(f"Volatility: {summary.get('volatility', 'N/A')}")
```

## Testing

Both modules include self-test functionality:

```bash
# Test technical analysis
python src/technical_analysis.py

# Test enhanced risk manager
python src/enhanced_risk_manager.py
```

## Configuration

### Technical Analysis Config

```python
tech_config = {
    'sma_short': 20,
    'sma_long': 50,
    'rsi_period': 14,
    'rsi_oversold': 30,
    'rsi_overbought': 70,
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,
    'bb_period': 20,
    'atr_period': 14
}

tech_engine = TechnicalAnalysisEngine(config=tech_config)
```

### Risk Management Config

```python
risk_config = {
    'initial_capital': 100000,
    'risk_tolerance': 0.02,  # 2% per trade
    'max_position_size': 0.1,  # 10% max
    'max_daily_loss': 0.05,  # 5% daily limit
    'max_drawdown': 0.20,  # 20% max drawdown
    'max_consecutive_losses': 3,
    'circuit_breaker_pause_hours': 1,
    'kelly_fraction': 0.25,
    'min_trade_confidence': 0.65
}

risk_mgr = EnhancedRiskManager(config=risk_config)
```

## Benefits

### From TradeBridge Integration:

1. **Technical Analysis**: Professional-grade technical indicators supplement PDF analysis
2. **Kelly Criterion**: Mathematically optimal position sizing
3. **Circuit Breakers**: Automatic protection against catastrophic losses
4. **Performance Metrics**: Sharpe/Sortino ratios, VaR, profit factor
5. **ATR-based Stops**: Dynamic stop losses based on market volatility
6. **Multi-Strategy**: Combine PDF insights with technical signals

### Hybrid Approach:

The trading bot now combines:
- **Fundamental Analysis** (from PDF documents) - unique feature
- **Technical Analysis** (from price data) - TradeBridge feature
- **Risk Management** (institutional-grade) - TradeBridge feature
- **Performance Tracking** (comprehensive metrics) - TradeBridge feature

This creates a more robust, professional trading system!

## Next Steps

1. **Data Integration**: Connect to real-time price data sources (WebSocket)
2. **Backtesting**: Test strategies on historical data
3. **Monitoring**: Add Telegram bot or web dashboard
4. **Database**: Migrate from JSON to PostgreSQL
5. **More Strategies**: Add more technical strategies (momentum, breakout, etc.)

## Support

For issues or questions, refer to:
- `TRADEBRIDGE_COMPARISON.md` - Full comparison document
- `src/technical_analysis.py` - Technical analysis implementation
- `src/enhanced_risk_manager.py` - Risk management implementation
