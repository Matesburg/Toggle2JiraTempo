"""
Main entry point for Toggle to Jira Tempo sync CLI application.
"""

import sys
import logging
from datetime import datetime
from pathlib import Path

# Setup logging with UTF-8 support
log_dir = Path(__file__).parent / 'logs'
log_dir.mkdir(exist_ok=True)

log_filename = log_dir / f"sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Create formatters
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# File handler with UTF-8
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Console handler with error handling for encoding issues
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)

logger = logging.getLogger(__name__)

from config import get_config
from toggle_api import ToggleAPI
from jira_api import JiraAPI
from db import get_db
from sync_engine import SyncEngine
from ui import ReviewUI


def main():
    """Main CLI entry point."""
    
    print("\n" + "="*80)
    print("TOGGLE TO JIRA TEMPO SYNC TOOL")
    print("="*80)
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = get_config()
        logger.info("[OK] Configuration loaded successfully")
        
        # Initialize API clients
        logger.info("Initializing API clients...")
        toggle_api = ToggleAPI(config.toggle_api_token, config.toggle_workspace_id)
        jira_api = JiraAPI(config.jira_url, config.jira_email, config.jira_api_token)
        
        # Test API connections
        print("\n🔗 Testing API Connections...")
        if not jira_api.test_connection():
            print("✗ Jira API connection failed. Check credentials in .env")
            return 1
        print("✓ Jira API connected")
        
        # Initialize database
        logger.info("Initializing database...")
        db = get_db()
        logger.info("[OK] Database initialized")
        
        # Get sync start date
        print("\n📅 Sync Date Range")
        print("-" * 80)
        
        last_watermark = db.get_last_watermark()
        
        if last_watermark:
            # Subsequent run - use first day of the month from last watermark
            print(f"Last sync: {last_watermark}")
            
            # Parse watermark to extract year and month
            try:
                watermark_dt = datetime.fromisoformat(last_watermark.replace('Z', '+00:00'))
                # Set start_date to first day of that month
                start_date = watermark_dt.replace(day=1).strftime('%Y-%m-%d')
                print(f"Syncing from first day of month: {start_date}")
            except (ValueError, AttributeError):
                # Fallback if parsing fails
                start_date = last_watermark
                print(f"Syncing entries since: {start_date}")
            
            is_first_run = False
        else:
            # First run - ask user for start date
            print("No previous sync found. This is the first run.")
            print(f"Default start date: {config.first_sync_date}")
            
            user_date = input("Enter sync start date (YYYY-MM-DD) or press Enter for default: ").strip()
            start_date = user_date if user_date else config.first_sync_date
            is_first_run = True
        
        # Fetch entries from Toggle
        print(f"\n📥 Fetching Toggle Entries...")
        print("-" * 80)
        logger.info(f"Fetching entries from {start_date}")
        
        try:
            toggle_entries = toggle_api.get_time_entries(start_date)
            print(f"✓ Retrieved {len(toggle_entries)} entries from Toggle")
            logger.info(f"Retrieved {len(toggle_entries)} Toggle entries")
        except Exception as e:
            print(f"✗ Failed to fetch Toggle entries: {e}")
            logger.error(f"Failed to fetch Toggle entries: {e}")
            return 1
        
        if not toggle_entries:
            print("ℹ No entries found for sync period")
            logger.info("No entries found in Toggle for sync period")
            return 0
        
        # Initialize sync engine
        print(f"\n⚙️ Preparing Entries for Sync...")
        print("-" * 80)
        logger.info("Preparing entries for sync")
        
        sync_engine = SyncEngine(toggle_api, jira_api, db)
        prepared_entries = sync_engine.prepare_entries(toggle_entries)
        
        logger.info(f"Prepared {len(prepared_entries)} entries")
        
        # Build review UI
        review_ui = ReviewUI()
        
        for toggle_id, prep_data in prepared_entries.items():
            review_ui.add_entry(
                prep_data['entry'],
                prep_data['status'],
                prep_data['validation_status'],
                prep_data['issue_key'],
                prep_data['error_msg']
            )
        
        # Display review
        review_ui.display_summary()
        review_ui.display_sync_entries()
        
        # Handle invalid entries
        corrections = {}
        if review_ui.invalid_entries:
            review_ui.display_invalid_entries()
            corrections = review_ui.prompt_for_invalid_entries()
        
        # Handle conflicts
        conflicts_decisions = {}
        if review_ui.conflicted_entries:
            review_ui.display_conflicts()
            conflicts_decisions = review_ui.prompt_for_conflicts()
        
        # Ask for final approval
        approval = review_ui.prompt_for_approval()
        
        if approval == 'cancel':
            print("\n❌ Sync cancelled by user")
            logger.info("Sync cancelled by user")
            return 0
        
        # Execute sync
        print(f"\n" + "="*80)
        print("EXECUTING SYNC")
        print("="*80)
        
        dry_run = (approval == 'dry_run')
        
        if dry_run:
            print("🔍 Running in DRY-RUN mode (no changes will be made)")
        else:
            print("🚀 Syncing entries to Jira...")
        
        stats = sync_engine.execute_sync(
            prepared_entries,
            corrections=corrections,
            conflicts_decisions=conflicts_decisions,
            dry_run=dry_run
        )
        
        # Display results
        review_ui.display_sync_results(stats)
        
        logger.info(f"Sync run {sync_engine.sync_run_id} completed. Stats: {stats}")
        
        # Log to database
        db.log_sync_run(
            sync_engine.sync_run_id,
            stats['attempted'],
            stats['synced'],
            stats['skipped'],
            stats['failed'],
            stats['failures'] if stats['failures'] else None
        )
        
        print(f"\n📝 Log saved to: {log_filename}")
        print("="*80)
        
        # Return appropriate exit code
        return 0 if stats['failed'] == 0 else 1
    
    except KeyError as e:
        print(f"\n✗ Configuration error: missing setting {e}")
        print("Please check your .env file. See .env.example for template.")
        logger.error(f"Configuration error: {e}")
        return 1
    
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1
    
    finally:
        # Cleanup
        if 'db' in locals():
            db.close()
            logger.info("Database connection closed")


if __name__ == '__main__':
    sys.exit(main())
