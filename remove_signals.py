"""
Utility to manually remove signals and revert their impact on equity and performance

Usage:
    python remove_signals.py                    # Interactive mode - select signals to remove
    python remove_signals.py --list            # List all historical signals
    python remove_signals.py --id SIGNAL_ID    # Remove specific signal by ID
    
Examples:
    # Remove multiple signals at once (interactive)
    python remove_signals.py
    > Enter signal number(s): 1,3,5
    
    # Remove single signal by ID
    python remove_signals.py --id 20260202_143022_XMRUSDT
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from loguru import logger

# Configure simple logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="<level>{message}</level>")

# File paths
DATA_DIR = Path('data')
SIGNALS_HISTORY_FILE = DATA_DIR / 'signals_history.json'
TRADE_HISTORY_FILE = DATA_DIR / 'trade_history.json'
PERFORMANCE_FILE = DATA_DIR / 'performance.json'
BACKUP_DIR = DATA_DIR / 'backups'

class SignalRemover:
    """Remove signals and revert their impact"""
    
    def __init__(self):
        # Check if files are accessible before loading
        self._check_file_access()
        
        self.signals_history = self._load_json(SIGNALS_HISTORY_FILE, [])
        self.trade_history = self._load_json(TRADE_HISTORY_FILE, [])
        self.performance = self._load_json(PERFORMANCE_FILE, {})
        
        # Ensure backup directory exists
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    def _check_file_access(self):
        """Check if data files are accessible (not locked)"""
        locked_files = []
        
        for filepath in [SIGNALS_HISTORY_FILE, TRADE_HISTORY_FILE, PERFORMANCE_FILE]:
            if filepath.exists():
                try:
                    # Try to open in read+write mode to check if locked
                    with open(filepath, 'r+') as f:
                        pass
                except PermissionError:
                    locked_files.append(filepath.name)
                except Exception:
                    pass
        
        if locked_files:
            logger.error("\n" + "="*70)
            logger.error("⚠️  ERROR: Cannot access the following files:")
            for filename in locked_files:
                logger.error(f"   • {filename}")
            logger.error("\n🔧 SOLUTIONS:")
            logger.error("   1. Stop the trading bot if it's running")
            logger.error("   2. Close files if open in VS Code or other editors")
            logger.error("   3. Close any JSON viewers")
            logger.error("="*70 + "\n")
            sys.exit(1)
    
    def _load_json(self, filepath: Path, default):
        """Load JSON file with error handling"""
        try:
            if filepath.exists():
                with open(filepath, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {filepath}: {e}")
        return default
    
    def _save_json(self, filepath: Path, data):
        """Save JSON file"""
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except PermissionError:
            logger.error(f"❌ Permission denied: {filepath}")
            logger.error(f"   File is locked or open in another program!")
            logger.error(f"   → Stop the bot if it's running")
            logger.error(f"   → Close the file if open in editor/viewer")
            return False
        except Exception as e:
            logger.error(f"Error saving {filepath}: {e}")
            return False
    
    def _create_backup(self):
        """Create backup of all data files before making changes"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for file in [SIGNALS_HISTORY_FILE, TRADE_HISTORY_FILE, PERFORMANCE_FILE]:
            if file.exists():
                backup_file = BACKUP_DIR / f"{file.stem}_backup_{timestamp}.json"
                try:
                    with open(file, 'r') as src:
                        data = json.load(src)
                    with open(backup_file, 'w') as dst:
                        json.dump(data, dst, indent=2)
                except Exception as e:
                    logger.error(f"Failed to backup {file}: {e}")
                    return False
        
        logger.info(f"✓ Backup created in {BACKUP_DIR}")
        return True
    
    def list_signals(self):
        """Display all historical signals"""
        if not self.signals_history:
            print("\nNo historical signals found.")
            return
        
        print("\n" + "="*100)
        print("HISTORICAL SIGNALS")
        print("="*100)
        
        for idx, signal in enumerate(self.signals_history, 1):
            pnl = signal.get('realized_pnl', 0)
            pnl_symbol = "💰" if pnl > 0 else "💸"
            
            print(f"\n{idx}. {pnl_symbol} {signal['symbol']} - {signal['direction'].upper()}")
            print(f"   Signal ID: {signal['signal_id']}")
            print(f"   Entry: ${signal['entry_price']:.4f}")
            print(f"   Stop Loss: ${signal['stop_loss']:.4f}")
            print(f"   Realized P&L: ${pnl:+.2f}")
            print(f"   Exit Reason: {signal.get('exit_reason', 'N/A')}")
            print(f"   Entry Time: {signal.get('entry_time', 'N/A')}")
            print(f"   Exit Time: {signal.get('close_time', 'N/A')}")
        
        print("\n" + "="*100)
        print(f"Total Signals: {len(self.signals_history)}")
        print(f"Total P&L: ${sum(s.get('realized_pnl', 0) for s in self.signals_history):+.2f}")
        print("="*100 + "\n")
    
    def remove_signal_by_id(self, signal_id: str) -> bool:
        """Remove signal by signal ID"""
        # Find signal in history
        signal = None
        for s in self.signals_history:
            if s['signal_id'] == signal_id:
                signal = s
                break
        
        if not signal:
            logger.error(f"Signal ID '{signal_id}' not found")
            return False
        
        return self._remove_signal(signal)
    
    def remove_signal_interactive(self):
        """Interactive signal removal"""
        if not self.signals_history:
            print("\nNo historical signals to remove.")
            return
        
        self.list_signals()
        
        try:
            choice = input("\nEnter signal number(s) to remove (comma-separated, or 'q' to quit): ").strip()
            
            if choice.lower() == 'q':
                print("Cancelled.")
                return
            
            # Parse multiple selections
            selections = [s.strip() for s in choice.split(',')]
            signals_to_remove = []
            
            for sel in selections:
                try:
                    idx = int(sel) - 1
                    if 0 <= idx < len(self.signals_history):
                        signals_to_remove.append(self.signals_history[idx])
                    else:
                        print(f"Invalid selection: {sel}")
                except ValueError:
                    print(f"Invalid input: {sel}")
            
            if not signals_to_remove:
                print("No valid signals selected.")
                return
            
            # Show summary and confirm
            print(f"\n⚠️  You are about to remove {len(signals_to_remove)} signal(s):")
            total_pnl_impact = 0
            for signal in signals_to_remove:
                pnl = signal.get('realized_pnl', 0)
                total_pnl_impact += pnl
                print(f"   • {signal['symbol']} {signal['direction'].upper()} | P&L: ${pnl:+.2f}")
            
            print(f"\nTotal P&L impact to revert: ${total_pnl_impact:+.2f}")
            confirm = input("\nAre you sure? (yes/no): ").strip().lower()
            
            if confirm == 'yes':
                success_count = 0
                for signal in signals_to_remove:
                    if self._remove_signal(signal):
                        success_count += 1
                
                print(f"\n✅ Successfully removed {success_count}/{len(signals_to_remove)} signals")
            else:
                print("Cancelled.")
                
        except ValueError:
            print("Invalid input.")
        except KeyboardInterrupt:
            print("\nCancelled.")
    
    def _remove_signal(self, signal: Dict) -> bool:
        """Remove signal and revert its impact"""
        signal_id = signal['signal_id']
        pnl = signal.get('realized_pnl', 0)
        
        logger.info(f"\n{'='*70}")
        logger.info(f"REMOVING SIGNAL: {signal['symbol']} {signal['direction'].upper()}")
        logger.info(f"Signal ID: {signal_id}")
        logger.info(f"P&L to revert: ${pnl:+.2f}")
        logger.info(f"{'='*70}\n")
        
        # Create backup first
        if not self._create_backup():
            logger.error("Backup failed - aborting removal")
            return False
        
        # 1. Revert equity impact
        if 'equity' in self.performance:
            old_equity = self.performance['equity']
            new_equity = old_equity - pnl
            self.performance['equity'] = new_equity
            logger.info(f"✓ Equity reverted: ${old_equity:.2f} → ${new_equity:.2f} ({pnl:+.2f})")
        
        # 2. Revert daily PnL if signal was today
        signal_date = None
        if 'close_time' in signal:
            try:
                signal_date = datetime.fromisoformat(signal['close_time']).date()
            except:
                pass
        
        if signal_date == datetime.now().date() and 'daily_pnl' in self.performance:
            old_daily_pnl = self.performance['daily_pnl']
            new_daily_pnl = old_daily_pnl - pnl
            self.performance['daily_pnl'] = new_daily_pnl
            logger.info(f"✓ Daily P&L reverted: ${old_daily_pnl:.2f} → ${new_daily_pnl:.2f}")
        
        # 3. Revert consecutive losses if it was a loss
        if pnl < 0 and 'consecutive_losses' in self.performance:
            old_losses = self.performance['consecutive_losses']
            new_losses = max(0, old_losses - 1)
            self.performance['consecutive_losses'] = new_losses
            logger.info(f"✓ Consecutive losses adjusted: {old_losses} → {new_losses}")
        
        # 4. Remove from signals history
        self.signals_history = [s for s in self.signals_history if s['signal_id'] != signal_id]
        logger.info(f"✓ Removed from signals history")
        
        # 5. Remove from trade history
        old_trade_count = len(self.trade_history)
        self.trade_history = [t for t in self.trade_history if t.get('signal_id') != signal_id]
        new_trade_count = len(self.trade_history)
        
        if old_trade_count != new_trade_count:
            logger.info(f"✓ Removed from trade history")
        
        # 6. Save all changes
        success = True
        success &= self._save_json(SIGNALS_HISTORY_FILE, self.signals_history)
        success &= self._save_json(TRADE_HISTORY_FILE, self.trade_history)
        success &= self._save_json(PERFORMANCE_FILE, self.performance)
        
        if success:
            logger.info(f"\n✅ Signal {signal_id} successfully removed!")
            logger.info(f"📊 Impact reverted:")
            logger.info(f"   • Equity adjusted: {pnl:+.2f}")
            logger.info(f"   • Trade count: -{old_trade_count - new_trade_count}")
            logger.info(f"   • Backups saved to: {BACKUP_DIR}")
            logger.info(f"\n{'='*70}\n")
            return True
        else:
            logger.error("Failed to save changes - check backups in data/backups/")
            return False

def main():
    """Main entry point"""
    remover = SignalRemover()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--list':
            remover.list_signals()
        elif sys.argv[1] == '--id' and len(sys.argv) > 2:
            signal_id = sys.argv[2]
            remover.remove_signal_by_id(signal_id)
        else:
            print("Usage:")
            print("  python remove_signals.py               # Interactive mode")
            print("  python remove_signals.py --list       # List all signals")
            print("  python remove_signals.py --id ID      # Remove by signal ID")
    else:
        # Interactive mode
        remover.remove_signal_interactive()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
