"""
Core sync engine logic for orchestrating Toggle to Jira sync operations.
"""

import logging
import uuid
from datetime import datetime
from validator import Validator, ConflictDetector
from db import SyncDatabase
from toggle_api import ToggleAPI
from jira_api import JiraAPI

logger = logging.getLogger(__name__)


class SyncEngine:
    """Main sync engine for Toggle to Jira transfers."""
    
    def __init__(self, toggle_api, jira_api, db):
        self.toggle_api = toggle_api
        self.jira_api = jira_api
        self.db = db
        self.sync_run_id = str(uuid.uuid4())[:8]
        
        # Stats tracking
        self.stats = {
            'attempted': 0,
            'synced': 0,
            'skipped': 0,
            'failed': 0,
            'failures': []
        }
    
    def prepare_entries(self, entries):
        """
        Prepare entries for sync with validation and conflict detection.
        
        Args:
            entries: List of Toggle entries
        
        Returns:
            Dict mapping toggle_id to entry review data
        """
        prepared = {}
        
        for entry in entries:
            self.stats['attempted'] += 1
            
            # Calculate hash BEFORE rounding (to detect any changes in original data)
            entry_hash = Validator.calculate_entry_hash(entry)
            
            # Round seconds up to whole minutes (Jira Tempo doesn't handle seconds)
            entry['duration'] = Validator.round_seconds_to_minutes(entry['duration'])
            
            # Try to extract issue key from project name
            issue_key, parse_success = Validator.extract_issue_key(entry['project_name'])
            
            if not parse_success:
                logger.warning(f"Entry {entry['id']}: Could not parse issue from project '{entry['project_name']}'")
                prepared[entry['id']] = {
                    'entry': entry,
                    'status': 'parse_error',
                    'issue_key': None,
                    'validation_status': 'parse_error',
                    'error_msg': f"Could not extract Jira issue key from project name: {entry['project_name']}",
                    'hash': entry_hash,
                }
                continue
            
            # Check if issue exists in Jira
            cache_result = self.db.check_issue_cache(issue_key)
            
            if cache_result:
                # Use cached validation
                issue_exists = cache_result['is_valid'] == 1
                logger.debug(f"Entry {entry['id']}: Using cached validation for {issue_key}")
            else:
                # Validate against Jira
                issue_exists = self.jira_api.validate_issue_exists(issue_key)
                logger.debug(f"Entry {entry['id']}: Validated {issue_key} in Jira - exists: {issue_exists}")
                
                # Cache the result
                error_reason = None if issue_exists else "Issue not found in Jira"
                self.db.cache_issue_validation(issue_key, issue_exists, error_reason)
            
            if not issue_exists:
                logger.warning(f"Entry {entry['id']}: Issue {issue_key} not found in Jira")
                prepared[entry['id']] = {
                    'entry': entry,
                    'status': 'invalid_issue',
                    'issue_key': issue_key,
                    'validation_status': 'invalid_issue',
                    'error_msg': f"Issue {issue_key} not found in Jira",
                    'hash': entry_hash,
                }
                continue
            
            # Check for existing worklog mapping (deduplication)
            existing_mapping = self.db.get_worklog_mapping(entry['id'])
            
            # Check if entry was previously stored and has been modified
            stored_entry = self.db.get_toggle_entry(entry['id'])
            entry_modified = False
            
            if stored_entry:
                stored_hash = stored_entry['local_hash']
                entry_modified = ConflictDetector.needs_update(entry_hash, stored_hash)
                if entry_modified:
                    logger.info(f"Entry {entry['id']}: Modified since last sync (update)")
            
            if existing_mapping and not entry_modified:
                # Entry was synced before and hasn't changed
                status = 'duplicate'
                logger.info(f"Entry {entry['id']}: Already synced (duplicate)")
            elif existing_mapping and entry_modified:
                # Entry was synced before but has changed - needs update
                status = 'update'
                logger.info(f"Entry {entry['id']}: Previously synced but modified (update)")
            else:
                # New entry
                status = 'new'
                logger.info(f"Entry {entry['id']}: New entry ready for sync")
            
            prepared[entry['id']] = {
                'entry': entry,
                'status': status,
                'issue_key': issue_key,
                'validation_status': 'valid',
                'error_msg': None,
                'hash': entry_hash,
            }
        
        logger.info(f"Prepared {len(prepared)} entries for review")
        return prepared
    
    def sync_entry(self, toggle_id, entry_data, issue_key, dry_run=False):
        """
        Sync a single Toggle entry to Jira.
        
        Args:
            toggle_id: Toggle entry ID
            entry_data: Toggle entry dict
            issue_key: Target Jira issue key
            dry_run: If True, don't actually create/update
        
        Returns:
            Tuple of (success: bool, worklog_id: str or None, error: str or None)
        """
        try:
            # Convert timestamps
            jira_timestamp = Validator.convert_toggle_timestamp_to_jira(entry_data['start'])
            
            # Use Toggle description as Jira worklog comment
            description = entry_data.get('description', '')
            
            # Check for existing worklog mapping
            existing_mapping = self.db.get_worklog_mapping(toggle_id)
            
            if dry_run:
                # Format duration nicely
                duration_formatted = Validator.format_seconds_to_jira_format(entry_data['duration'])
                desc_display = description[:60] + '...' if len(description) > 60 else description
                logger.info(f"[DRY-RUN] Would create worklog:")
                logger.info(f"  - Issue: {issue_key}")
                logger.info(f"  - Date: {jira_timestamp}")
                logger.info(f"  - Duration: {duration_formatted}")
                logger.info(f"  - Description: {desc_display if desc_display else '(no description)'}")
                return True, None, None
            
            if existing_mapping and existing_mapping['status'] == 'synced':
                # Update existing worklog
                logger.info(f"Updating worklog {existing_mapping['jira_worklog_id']} for {issue_key}")
                success = self.jira_api.update_worklog(
                    issue_key,
                    existing_mapping['jira_worklog_id'],
                    jira_timestamp,
                    entry_data['duration'],
                    description
                )
                return success, existing_mapping['jira_worklog_id'], None
            else:
                # Create new worklog
                logger.info(f"Creating new worklog for {issue_key}")
                worklog_id = self.jira_api.create_worklog(
                    issue_key,
                    jira_timestamp,
                    entry_data['duration'],
                    description
                )
                return worklog_id is not None, worklog_id, None
        
        except Exception as e:
            error_msg = f"Failed to sync entry {toggle_id}: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
    
    def execute_sync(self, prepared_entries, corrections=None, conflicts_decisions=None, dry_run=False):
        """
        Execute the sync for all prepared entries.
        
        Args:
            prepared_entries: Dict from prepare_entries()
            corrections: Dict of toggle_id -> corrected_issue_key or 'skip'/'ignore'
            conflicts_decisions: Dict of toggle_id -> 'skip'/'overwrite'
            dry_run: If True, don't actually create/update, just show what would happen
        
        Returns:
            Stats dict with sync results
        """
        if corrections is None:
            corrections = {}
        if conflicts_decisions is None:
            conflicts_decisions = {}
        
        logger.info(f"Starting sync execution (dry_run={dry_run})")
        
        for toggle_id, prep_data in prepared_entries.items():
            status = prep_data['status']
            
            # Handle corrections for invalid issues
            if toggle_id in corrections:
                correction = corrections[toggle_id]
                if correction == 'skip':
                    logger.info(f"Skipping entry {toggle_id} per user request")
                    self.stats['skipped'] += 1
                    continue
                elif correction == 'ignore':
                    # Use the original issue key anyway
                    prep_data['validation_status'] = 'ignored'
                else:
                    # It's a corrected issue key
                    prep_data['issue_key'] = correction
                    status = 'new'
            
            # Handle conflict decisions
            if toggle_id in conflicts_decisions and conflicts_decisions[toggle_id] == 'skip':
                logger.info(f"Skipping entry {toggle_id} due to conflict (user decision)")
                self.stats['skipped'] += 1
                continue
            
            # Skip duplicates and parse errors
            if status == 'duplicate':
                logger.info(f"Skipping duplicate entry {toggle_id}")
                self.stats['skipped'] += 1
                continue
            
            if status == 'parse_error':
                logger.info(f"Skipping entry {toggle_id} with parse error")
                self.stats['skipped'] += 1
                continue
            
            if status in ['invalid_issue', 'parse_error'] and prep_data['validation_status'] != 'ignored':
                logger.info(f"Skipping invalid entry {toggle_id}")
                self.stats['skipped'] += 1
                continue
            
            # Attempt sync
            entry_data = prep_data['entry']
            issue_key = prep_data['issue_key']
            
            success, worklog_id, error = self.sync_entry(
                toggle_id,
                entry_data,
                issue_key,
                dry_run=dry_run
            )
            
            if success:
                self.stats['synced'] += 1
                
                # Only log details in production mode (already logged in dry_run by sync_entry)
                if not dry_run:
                    duration_formatted = Validator.format_seconds_to_jira_format(entry_data['duration'])
                    desc_display = entry_data.get('description', '(no description)')
                    desc_display = desc_display[:60] + '...' if len(desc_display) > 60 else desc_display
                    jira_timestamp = Validator.convert_toggle_timestamp_to_jira(entry_data['start'])
                    
                    logger.info(f"[OK] Entry {toggle_id} synced successfully")
                    logger.info(f"  - Issue: {issue_key}")
                    logger.info(f"  - Date: {jira_timestamp}")
                    logger.info(f"  - Duration: {duration_formatted}")
                    logger.info(f"  - Description: {desc_display}")
                
                # Save to database only if not dry-run
                if not dry_run:
                    self.db.save_toggle_entry({
                        **entry_data,
                        'hash': prep_data['hash']
                    })
                    self.db.save_worklog_mapping(
                        toggle_id,
                        worklog_id,
                        issue_key,
                        'synced'
                    )
            else:
                self.stats['failed'] += 1
                self.stats['failures'].append({'toggle_id': toggle_id, 'error': error})
                logger.error(f"[ERROR] Entry {toggle_id} failed: {error}")
        
        # Update watermark to the latest entry date processed (whether synced or skipped)
        if prepared_entries and not dry_run:
            # Find the latest entry date from all processed entries
            latest_date = None
            for toggle_id, prep_data in prepared_entries.items():
                entry_data = prep_data['entry']
                entry_date = entry_data.get('start')
                if entry_date:
                    if latest_date is None or entry_date > latest_date:
                        latest_date = entry_date
            
            if latest_date:
                self.db.set_watermark(latest_date)
                logger.info(f"Watermark updated to {latest_date} for next sync")
        
        logger.info(f"Sync execution complete: {self.stats['synced']} synced, {self.stats['failed']} failed")
        return self.stats
