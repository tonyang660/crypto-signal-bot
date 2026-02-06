"""
Paper Trading Setup Utility

Helps prepare for paper trading mode by managing history files.
Run this before enabling PAPER_TRADING_ENABLED=true.
"""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime

def backup_existing_files():
    """Backup existing history files"""
    data_dir = Path('data')
    backup_dir = data_dir / 'backups' / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    files_to_backup = [
        'signals_history.json',
        'trade_history.json',
        'performance.json'
    ]
    
    backed_up = []
    for filename in files_to_backup:
        file_path = data_dir / filename
        if file_path.exists():
            backup_path = backup_dir / filename
            shutil.copy2(file_path, backup_path)
            backed_up.append(filename)
            print(f"✓ Backed up: {filename}")
    
    if backed_up:
        print(f"\n📦 Backup created: {backup_dir}")
        return backup_dir
    else:
        print("\n⚠️  No files to backup")
        return None

def check_paper_trading_files():
    """Check which files exist"""
    data_dir = Path('data')
    
    print("\n" + "="*70)
    print("📁 CURRENT FILE STATUS")
    print("="*70)
    
    files = {
        'Signal-Only Mode': [
            'signals_history.json',
            'trade_history.json',
            'performance.json'
        ],
        'Paper Trading Mode': [
            'signals_history_paper.json',
            'trade_history_paper.json',
            'paper_account.json'
        ]
    }
    
    for mode, file_list in files.items():
        print(f"\n{mode}:")
        for filename in file_list:
            file_path = data_dir / filename
            if file_path.exists():
                size = file_path.stat().st_size
                print(f"  ✓ {filename:<35} ({size:,} bytes)")
            else:
                print(f"  ✗ {filename:<35} (not found)")

def initialize_paper_trading_files():
    """Create fresh paper trading history files"""
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    
    # Initialize empty histories
    files_to_create = {
        'signals_history_paper.json': [],
        'trade_history_paper.json': []
    }
    
    created = []
    for filename, content in files_to_create.items():
        file_path = data_dir / filename
        if not file_path.exists():
            with open(file_path, 'w') as f:
                json.dump(content, f, indent=2)
            created.append(filename)
            print(f"✓ Created: {filename}")
        else:
            print(f"⚠️  Already exists: {filename}")
    
    # paper_account.json will be created automatically by bot
    print(f"\n✓ Paper trading history files ready")
    print(f"ℹ️  paper_account.json will be created on first bot run")
    
    return created

def show_menu():
    """Display interactive menu"""
    print("\n" + "="*70)
    print("📊 PAPER TRADING SETUP")
    print("="*70)
    print("\nWhat would you like to do?\n")
    print("1. Check current file status")
    print("2. Backup existing files (recommended before switching)")
    print("3. Initialize fresh paper trading files")
    print("4. Do all: Backup → Initialize → Check status")
    print("5. Exit")
    print("\n" + "="*70)
    
    choice = input("\nEnter choice (1-5): ").strip()
    return choice

def main():
    """Main entry point"""
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                  PAPER TRADING SETUP UTILITY                     ║
╚══════════════════════════════════════════════════════════════════╝

This utility helps you prepare for paper trading mode.

IMPORTANT:
- Paper trading uses separate history files
- Old simulated signals stay in: signals_history.json
- New paper trades go to: signals_history_paper.json
- This prevents mixing simulated vs. realistic execution data

""")
    
    while True:
        choice = show_menu()
        
        if choice == '1':
            check_paper_trading_files()
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            print("\n🔄 Backing up existing files...")
            backup_dir = backup_existing_files()
            if backup_dir:
                print(f"\n✅ Files safely backed up to: {backup_dir}")
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            print("\n🔄 Initializing paper trading files...")
            initialize_paper_trading_files()
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            print("\n🔄 Running complete setup...\n")
            
            # Step 1: Backup
            print("Step 1: Backing up existing files...")
            backup_dir = backup_existing_files()
            
            # Step 2: Initialize
            print("\nStep 2: Initializing paper trading files...")
            initialize_paper_trading_files()
            
            # Step 3: Status
            print("\nStep 3: Checking status...")
            check_paper_trading_files()
            
            print("\n" + "="*70)
            print("✅ SETUP COMPLETE!")
            print("="*70)
            print("\nNext steps:")
            print("1. Set PAPER_TRADING_ENABLED=true in .env")
            print("2. Run: python -m src.main")
            print("3. Monitor: python check_paper_trading.py")
            print("\n" + "="*70)
            
            input("\nPress Enter to exit...")
            break
        
        elif choice == '5':
            print("\n👋 Goodbye!\n")
            break
        
        else:
            print("\n❌ Invalid choice. Please enter 1-5.")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Cancelled by user.\n")
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
