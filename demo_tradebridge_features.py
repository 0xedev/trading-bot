#!/usr/bin/env python3
"""
Demo: TradeBridge Features Integration
Demonstrates the new technical analysis and enhanced risk management features
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import our new modules
from src.technical_analysis import TechnicalAnalysisEngine, get_sample_data
from src.enhanced_risk_manager import EnhancedRiskManager


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def demo_technical_analysis():
    """Demonstrate technical analysis capabilities"""
    print_section("Technical Analysis Demo")
    
    # Initialize the technical analysis engine
    engine = TechnicalAnalysisEngine()
    print("✅ Technical Analysis Engine initialized")
    
    # Generate sample data
    symbol = "BTCUSDT"
    df = get_sample_data(symbol, periods=100)
    print(f"✅ Generated {len(df)} periods of sample data for {symbol}")
    print(f"   Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    
    # Calculate indicators
    df = engine.calculate_indicators(df)
    indicators = [col for col in df.columns if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    print(f"\n📊 Calculated {len(indicators)} technical indicators:")
    print(f"   {', '.join(indicators[:10])}...")
    
    # Get current market summary
    summary = engine.get_market_summary(df)
    print(f"\n📈 Market Summary for {symbol}:")
    print(f"   Price: ${summary['price']:,.2f}")
    print(f"   RSI: {summary.get('rsi', 'N/A'):.1f} ({summary.get('rsi_condition', 'N/A')})")
    print(f"   Trend: {summary.get('trend', 'N/A')}")
    print(f"   Volatility: {summary.get('volatility', 'N/A')} (ATR: ${summary.get('atr', 0):.2f})")
    
    # Generate trading signals
    signals = engine.generate_signals(df, symbol=symbol)
    print(f"\n🎯 Generated {len(signals)} trading signals:")
    for i, signal in enumerate(signals, 1):
        print(f"   {i}. {signal.action} - {signal.reason}")
        print(f"      Confidence: {signal.confidence:.2%} | Price: ${signal.price:.2f}")
        if signal.metadata:
            print(f"      Indicator: {signal.metadata.get('indicator', 'N/A')}")
    
    if len(signals) == 0:
        print("   ℹ️  No strong signals detected (market in neutral zone)")
    
    return signals, df


def demo_risk_management(signals, price_data):
    """Demonstrate enhanced risk management"""
    print_section("Enhanced Risk Management Demo")
    
    # Initialize risk manager with configuration
    config = {
        'initial_capital': 100000,
        'risk_tolerance': 0.02,
        'max_position_size': 0.10,
        'max_daily_loss': 0.05,
        'max_drawdown': 0.20,
        'max_consecutive_losses': 3,
        'kelly_fraction': 0.25,
        'min_trade_confidence': 0.65
    }
    
    risk_mgr = EnhancedRiskManager(config)
    print("✅ Enhanced Risk Manager initialized")
    print(f"   Initial Capital: ${config['initial_capital']:,}")
    print(f"   Risk Tolerance: {config['risk_tolerance']*100}% per trade")
    print(f"   Max Position Size: {config['max_position_size']*100}%")
    print(f"   Max Daily Loss: {config['max_daily_loss']*100}%")
    
    portfolio_value = config['initial_capital']
    
    # Check circuit breakers
    can_trade, reason = risk_mgr.check_circuit_breakers(portfolio_value)
    print(f"\n🚦 Circuit Breaker Check: {'✅ PASS' if can_trade else '🚨 FAIL'}")
    print(f"   Status: {reason}")
    
    # Calculate Kelly position size
    kelly_size = risk_mgr.kelly_position_size(
        win_rate=0.6,
        avg_win=0.05,
        avg_loss=0.03,
        signal_confidence=0.75
    )
    print(f"\n📊 Kelly Criterion Position Sizing:")
    print(f"   Win Rate: 60% | Avg Win: 5% | Avg Loss: 3%")
    print(f"   Kelly Position Size: {kelly_size*100:.1f}%")
    print(f"   Dollar Amount: ${kelly_size * portfolio_value:,.2f}")
    
    # Process signals with risk management
    if signals:
        print(f"\n💼 Processing {len(signals)} signals with risk controls:")
        
        for i, signal in enumerate(signals[:3], 1):  # Process first 3 signals
            print(f"\n   Signal {i}: {signal.action} {signal.symbol}")
            print(f"   Confidence: {signal.confidence:.2%}")
            
            # Calculate position size
            atr = price_data['atr'].iloc[-1] if 'atr' in price_data.columns else None
            position_size = risk_mgr.calculate_position_size(
                signal=signal,
                portfolio_value=portfolio_value,
                atr=atr
            )
            
            if position_size > 0:
                position_value = position_size * portfolio_value
                
                # Calculate stop loss
                stop_loss = risk_mgr.calculate_stop_loss(
                    entry_price=signal.price,
                    action=signal.action,
                    atr=atr
                )
                
                print(f"   ✅ Position Size: {position_size*100:.1f}% (${position_value:,.2f})")
                print(f"   🛡️  Stop Loss: ${stop_loss:.2f}")
                print(f"   📍 Entry Price: ${signal.price:.2f}")
                
                # Calculate risk per trade
                if signal.action == 'BUY':
                    risk_amount = (signal.price - stop_loss) * (position_value / signal.price)
                else:
                    risk_amount = (stop_loss - signal.price) * (position_value / signal.price)
                
                print(f"   ⚠️  Risk Amount: ${abs(risk_amount):,.2f} ({abs(risk_amount)/portfolio_value*100:.2f}%)")
            else:
                print(f"   ❌ Signal rejected (confidence too low or risk too high)")
    
    # Simulate some trades to show performance tracking
    print(f"\n📈 Simulating Trade History:")
    np.random.seed(42)
    for i in range(10):
        pnl = np.random.randn() * 500
        risk_mgr.record_trade(
            symbol="BTCUSDT",
            action="BUY" if i % 2 == 0 else "SELL",
            entry_price=50000 + np.random.randn() * 1000,
            quantity=0.1,
            pnl=pnl
        )
    
    portfolio_value += sum(t.pnl for t in risk_mgr.trade_history)
    
    # Get comprehensive risk metrics
    metrics = risk_mgr.get_risk_metrics(portfolio_value)
    
    print(f"\n📊 Risk Metrics After 10 Trades:")
    print(f"   Portfolio Value: ${metrics['portfolio_value']:,.2f}")
    print(f"   Total Return: {((metrics['portfolio_value'] - config['initial_capital']) / config['initial_capital'] * 100):.2f}%")
    print(f"   Win Rate: {metrics['win_rate']*100:.1f}%")
    print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"   Avg Win: ${metrics['avg_win']:.2f}")
    print(f"   Avg Loss: ${metrics['avg_loss']:.2f}")
    print(f"   Current Drawdown: {metrics['drawdown']*100:.2f}%")
    print(f"   Consecutive Wins: {metrics['consecutive_wins']}")
    print(f"   Consecutive Losses: {metrics['consecutive_losses']}")
    
    if metrics['sharpe_ratio'] != 0:
        print(f"   Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    
    return risk_mgr, metrics


def demo_multi_strategy_combination():
    """Demonstrate combining multiple signal sources"""
    print_section("Multi-Strategy Signal Combination")
    
    print("🎯 Combining PDF Analysis with Technical Analysis:")
    print("\n   Strategy Sources:")
    print("   1. PDF Analysis (40% weight) - Fundamental insights from documents")
    print("   2. Technical Analysis (60% weight) - Price action and indicators")
    
    # Simulate PDF signals
    pdf_signals = [
        {'symbol': 'BTCUSDT', 'action': 'BUY', 'confidence': 0.8, 'source': 'PDF'},
    ]
    
    # Get technical signals
    engine = TechnicalAnalysisEngine()
    df = get_sample_data("BTCUSDT", periods=100)
    df = engine.calculate_indicators(df)
    tech_signals = engine.generate_signals(df, symbol="BTCUSDT")
    
    print(f"\n   📄 PDF Signals: {len(pdf_signals)}")
    for sig in pdf_signals:
        print(f"      - {sig['action']} {sig['symbol']} (conf: {sig['confidence']:.2%})")
    
    print(f"\n   📊 Technical Signals: {len(tech_signals)}")
    for sig in tech_signals[:3]:
        print(f"      - {sig.action} {sig.symbol} (conf: {sig.confidence:.2%}) - {sig.reason}")
    
    # Calculate combined conviction score
    weights = {'pdf': 0.4, 'technical': 0.6}
    
    buy_conviction = 0
    sell_conviction = 0
    
    for sig in pdf_signals:
        if sig['action'] == 'BUY':
            buy_conviction += sig['confidence'] * weights['pdf']
        elif sig['action'] == 'SELL':
            sell_conviction += sig['confidence'] * weights['pdf']
    
    for sig in tech_signals:
        if sig.action == 'BUY':
            buy_conviction += sig.confidence * weights['technical']
        elif sig.action == 'SELL':
            sell_conviction += sig.confidence * weights['technical']
    
    print(f"\n   🎯 Conviction Scores:")
    print(f"      BUY Conviction: {buy_conviction:.2%}")
    print(f"      SELL Conviction: {sell_conviction:.2%}")
    
    if buy_conviction > sell_conviction and buy_conviction > 0.6:
        final_action = "BUY"
        final_confidence = buy_conviction
    elif sell_conviction > buy_conviction and sell_conviction > 0.6:
        final_action = "SELL"
        final_confidence = sell_conviction
    else:
        final_action = "HOLD"
        final_confidence = max(buy_conviction, sell_conviction)
    
    print(f"\n   ✅ Final Decision: {final_action} (confidence: {final_confidence:.2%})")
    
    if final_confidence > 0.7:
        print(f"      🟢 Strong signal - Execute trade")
    elif final_confidence > 0.6:
        print(f"      🟡 Moderate signal - Consider trade")
    else:
        print(f"      🔴 Weak signal - Wait for better opportunity")


def main():
    """Run all demos"""
    print("\n" + "=" * 60)
    print("  TradeBridge Features Integration Demo")
    print("  Trading Bot Enhanced with Institutional Features")
    print("=" * 60)
    print("\nThis demo showcases new features inspired by TradeBridge:")
    print("  ✅ Technical Analysis (100+ indicators)")
    print("  ✅ Enhanced Risk Management (Kelly, VaR, Circuit Breakers)")
    print("  ✅ Multi-Strategy Signal Combination")
    print("  ✅ Performance Metrics (Sharpe, Sortino, Profit Factor)")
    
    try:
        # Demo 1: Technical Analysis
        signals, price_data = demo_technical_analysis()
        
        # Demo 2: Risk Management
        risk_mgr, metrics = demo_risk_management(signals, price_data)
        
        # Demo 3: Multi-Strategy Combination
        demo_multi_strategy_combination()
        
        # Summary
        print_section("Demo Complete")
        print("\n✨ Successfully demonstrated TradeBridge features!")
        print("\n📚 Next Steps:")
        print("   1. Review INTEGRATION_GUIDE.md for detailed integration steps")
        print("   2. Review TRADEBRIDGE_COMPARISON.md for full feature comparison")
        print("   3. Integrate these features into your trading workflow")
        print("   4. Configure risk parameters for your trading style")
        print("   5. Test with paper trading before going live")
        
        print("\n⚠️  Important Reminders:")
        print("   - Always test thoroughly in paper trading mode")
        print("   - Monitor risk metrics regularly")
        print("   - Respect circuit breakers and risk limits")
        print("   - Past performance doesn't guarantee future results")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    main()
