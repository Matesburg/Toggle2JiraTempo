"""
CLI UI for reviewing and approving sync entries before transfer.
"""

import logging
from datetime import datetime
from tabulate import tabulate
from validator import Validator
from collections import defaultdict

logger = logging.getLogger(__name__)


class ReviewUI:
    """CLI-based review interface for sync approval."""
    
    def __init__(self):
        self.entries_to_sync = []
        self.invalid_entries = []
        self.conflicted_entries = []
        self.duplicate_entries = []
    
    def add_entry(self, entry_data, status, validation_status=None, issue_key=None, error_msg=None):
        """
        Add entry to sync review list.
        
        Args:
            entry_data: Toggle entry dict
            status: 'new', 'update', 'duplicate', 'conflict', 'invalid', 'parse_error'
            validation_status: 'valid', 'invalid_issue', 'parse_error'
            issue_key: Extracted/corrected issue key
            error_msg: Error message if validation failed
        """
        review_item = {
            'toggle_id': entry_data.get('id'),
            'project_name': entry_data.get('project_name'),
            'issue_key': issue_key,
            'description': entry_data.get('description', '(no description)'),
            'duration': Validator.format_seconds_to_jira_format(entry_data.get('duration', 0)),
            'start': entry_data.get('start'),
            'status': status,
            'validation_status': validation_status,
            'error_msg': error_msg,
            'entry_data': entry_data,
        }
        
        # Categorize entries - duplicates go to separate list
        if status == 'duplicate':
            self.duplicate_entries.append(review_item)
        elif validation_status in ['invalid_issue', 'parse_error']:
            self.invalid_entries.append(review_item)
        elif status == 'conflict':
            self.conflicted_entries.append(review_item)
        else:
            self.entries_to_sync.append(review_item)
    
    def display_summary(self):
        """Display summary of entries ready for sync."""
        print("\n" + "="*80)
        print("SYNC REVIEW - Toggle Time Entries to Jira")
        print("="*80)
        
        total_entries = len(self.entries_to_sync) + len(self.invalid_entries) + len(self.conflicted_entries) + len(self.duplicate_entries)
        print(f"\n📊 Summary: {total_entries} entries found")
        print(f"  ✓ Ready to sync: {len(self.entries_to_sync)}")
        if self.duplicate_entries:
            print(f"  ⊘ Duplicates (already synced): {len(self.duplicate_entries)}")
        if self.invalid_entries:
            print(f"  ✗ Invalid issues: {len(self.invalid_entries)}")
        if self.conflicted_entries:
            print(f"  ⚠ Conflicts: {len(self.conflicted_entries)}")
    
    def _calculate_seconds_from_jira_format(self, jira_format_str):
        """
        Convert Jira format time string (e.g., '2h 30m', '1h', '30m') to seconds.
        
        Args:
            jira_format_str: Time in Jira format (e.g., '2h 30m')
            
        Returns:
            Total seconds as integer
        """
        total_seconds = 0
        parts = jira_format_str.split()
        
        for part in parts:
            if part.endswith('h'):
                total_seconds += int(part[:-1]) * 3600
            elif part.endswith('m'):
                total_seconds += int(part[:-1]) * 60
        
        return total_seconds
    
    def _seconds_to_display_format(self, seconds):
        """Convert seconds to display format (e.g., '2h 30m' or '45m')."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        
        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h"
        else:
            return f"{minutes}m"
    
    def _display_time_summaries(self):
        """Display weekly time summaries and total time using actual raw seconds (only for entries to sync)."""
        if not self.entries_to_sync:
            return
        
        # Group entries by week - only entries that will actually be synced
        weekly_totals = defaultdict(int)
        total_seconds = 0
        
        for entry in self.entries_to_sync:
            # Parse start datetime
            start_str = entry['start']
            try:
                start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                # Get week number (ISO week)
                year, week, _ = start_dt.isocalendar()
                week_key = f"{year}-W{week:02d}"
            except (ValueError, AttributeError):
                week_key = "Unknown"
            
            # Use raw seconds from original entry data (not the rounded format string)
            duration_seconds = entry['entry_data'].get('duration', 0)
            weekly_totals[week_key] += duration_seconds
            total_seconds += duration_seconds
        
        # Display weekly breakdown
        print(f"\n⏱️  Time Summary (entries to import):")
        print("-" * 80)
        
        week_data = []
        for week_key in sorted(weekly_totals.keys()):
            week_seconds = weekly_totals[week_key]
            week_display = self._seconds_to_display_format(week_seconds)
            week_data.append([week_key, week_display])
        
        if week_data:
            print(tabulate(week_data, headers=['Week', 'Total Time'], tablefmt='simple'))
        
        # Display total
        total_display = self._seconds_to_display_format(total_seconds)
        print(f"\n📊 Total Time to Import: {total_display}")
        print("="*80)
    
    def display_sync_entries(self):
        """Display entries ready for sync with dates, sorted by date ascending."""
        if not self.entries_to_sync:
            return
        
        print(f"\n✓ Entries Ready to Sync ({len(self.entries_to_sync)}):")
        print("-" * 80)
        
        # Sort entries by start date (ascending)
        sorted_entries = sorted(self.entries_to_sync, key=lambda e: e['start'] or '')
        
        table_data = []
        for idx, entry in enumerate(sorted_entries, 1):
            # Parse date from start timestamp
            start_str = entry['start']
            try:
                start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                date_str = start_dt.strftime('%Y-%m-%d %H:%M')
            except (ValueError, AttributeError):
                date_str = start_str[:16] if start_str else 'Unknown'
            
            table_data.append([
                idx,
                entry['issue_key'] or 'UNKNOWN',
                date_str,
                entry['description'][:35] + '...' if len(entry['description']) > 35 else entry['description'],
                entry['duration'],
                entry['status'].upper(),
            ])
        
        headers = ['#', 'Issue', 'Date/Time', 'Description', 'Duration', 'Type']
        print(tabulate(table_data, headers=headers, tablefmt='simple'))
        
        # Display time summaries after entries
        self._display_time_summaries()
    
    def display_invalid_entries(self):
        """Display entries with invalid issue keys."""
        if not self.invalid_entries:
            return
        
        print(f"\n✗ Invalid Issue Keys ({len(self.invalid_entries)}) - Action Required:")
        print("-" * 80)
        
        for idx, entry in enumerate(self.invalid_entries, 1):
            print(f"\n  {idx}. Toggle Entry #{entry['toggle_id']}")
            print(f"     Project: {entry['project_name']}")
            print(f"     Description: {entry['description']}")
            print(f"     Duration: {entry['duration']}")
            print(f"     ⚠ Issue: {entry['validation_status'].upper()}")
            if entry['error_msg']:
                print(f"     Error: {entry['error_msg']}")
    
    def display_conflicts(self):
        """Display entries with conflicts."""
        if not self.conflicted_entries:
            return
        
        print(f"\n⚠ Conflicts Detected ({len(self.conflicted_entries)}):")
        print("-" * 80)
        
        for idx, entry in enumerate(self.conflicted_entries, 1):
            print(f"\n  {idx}. Issue: {entry['issue_key']}")
            print(f"     Toggle Entry: #{entry['toggle_id']}")
            print(f"     Description: {entry['description']}")
            print(f"     ⚠ Worklog already exists in Jira for this date/issue")
    
    def prompt_for_invalid_entries(self):
        """
        Prompt user to handle invalid entries.
        
        Returns:
            Dict mapping toggle_id to action ('skip' or corrected issue_key)
        """
        if not self.invalid_entries:
            return {}
        
        corrections = {}
        print(f"\n" + "="*80)
        print("HANDLE INVALID ISSUES")
        print("="*80)
        
        for entry in self.invalid_entries:
            toggle_id = entry['toggle_id']
            print(f"\n\nToggle Entry #{toggle_id}: {entry['project_name']}")
            print(f"  Description: {entry['description']}")
            print(f"  Duration: {entry['duration']}")
            print(f"\nOptions:")
            print("  (s) Skip this entry")
            print("  (c) Correct issue key")
            print("  (i) Ignore and sync anyway (not recommended)")
            
            while True:
                choice = input("\nYour choice (s/c/i): ").strip().lower()
                
                if choice == 's':
                    corrections[toggle_id] = 'skip'
                    print("  → Skipped")
                    break
                elif choice == 'i':
                    corrections[toggle_id] = 'ignore'
                    print("  → Will attempt sync (may fail)")
                    break
                elif choice == 'c':
                    issue_key = input("  Enter correct issue key (e.g., PROJ-123): ").strip().upper()
                    if Validator.is_valid_issue_key_format(issue_key):
                        corrections[toggle_id] = issue_key
                        print(f"  → Corrected to {issue_key}")
                        # Update the entry's issue_key for later processing
                        entry['issue_key'] = issue_key
                        # Move from invalid to sync list
                        self.entries_to_sync.append(entry)
                        self.invalid_entries.remove(entry)
                        break
                    else:
                        print(f"  ✗ Invalid format. Expected format like PROJ-123")
                else:
                    print("  ✗ Invalid choice. Please enter s, c, or i")
        
        return corrections
    
    def prompt_for_conflicts(self):
        """
        Prompt user to handle conflicts (existing worklogs).
        
        Returns:
            Dict mapping toggle_id to action ('skip' or 'overwrite')
        """
        if not self.conflicted_entries:
            return {}
        
        decisions = {}
        print(f"\n" + "="*80)
        print("HANDLE CONFLICTS")
        print("="*80)
        
        for entry in self.conflicted_entries:
            toggle_id = entry['toggle_id']
            print(f"\n\nIssue {entry['issue_key']}: Worklog already exists")
            print(f"  Toggle Entry: #{toggle_id}")
            print(f"  Description: {entry['description']}")
            print(f"\nOptions:")
            print("  (s) Skip this entry (don't update)")
            print("  (o) Overwrite with Toggle data (trust Toggle as source of truth)")
            
            while True:
                choice = input("\nYour choice (s/o): ").strip().lower()
                
                if choice == 's':
                    decisions[toggle_id] = 'skip'
                    print("  → Skipped")
                    break
                elif choice == 'o':
                    decisions[toggle_id] = 'overwrite'
                    print("  → Will update with Toggle data")
                    # Move from conflicted to sync list
                    self.entries_to_sync.append(entry)
                    self.conflicted_entries.remove(entry)
                    break
                else:
                    print("  ✗ Invalid choice. Please enter s or o")
        
        return decisions
    
    def prompt_for_approval(self):
        """
        Prompt user for final sync approval.
        
        Returns:
            Boolean - True to proceed, False to cancel
        """
        print(f"\n" + "="*80)
        print("FINAL APPROVAL")
        print("="*80)
        print(f"\n✓ Ready to sync {len(self.entries_to_sync)} entries to Jira")
        
        if self.invalid_entries:
            print(f"⚠ {len(self.invalid_entries)} entries will be skipped (invalid issues)")
        if self.conflicted_entries:
            print(f"⚠ {len(self.conflicted_entries)} entries will be skipped (conflicts)")
        
        while True:
            choice = input("\nProceed with sync? (yes/no/dry-run): ").strip().lower()
            
            if choice in ['yes', 'y']:
                return 'sync'
            elif choice in ['no', 'n']:
                print("Sync cancelled by user")
                return 'cancel'
            elif choice in ['dry-run', 'dry']:
                print("Dry-run mode: showing what would happen without actual sync")
                return 'dry_run'
            else:
                print("✗ Invalid choice. Please enter 'yes', 'no', or 'dry-run'")
    
    def display_sync_results(self, results):
        """
        Display results after sync completes.
        
        Args:
            results: Dict with sync_run_id, synced, failed, skipped
        """
        print(f"\n" + "="*80)
        print("SYNC COMPLETE")
        print("="*80)
        print(f"\n✓ Synced: {results['synced']}")
        print(f"✗ Failed: {results['failed']}")
        print(f"⊘ Skipped: {results['skipped']}")
        
        if results['failed'] > 0:
            print(f"\n⚠ Some entries failed. Check logs for details.")
            print(f"   Run 'python main.py' again to retry failed entries.")
