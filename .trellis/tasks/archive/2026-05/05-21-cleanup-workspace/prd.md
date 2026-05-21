# brainstorm: Cleanup workspace and clear temporary files

## Goal

Safely clear temporary files, caches, and old sessions to reclaim space and maintain workspace hygiene.

## What I already know

*   `.pytest_cache`: Cache files.
*   `.scratch\sessions`: Old session files (dated JSON files).
*   `C:\Users\Admin\.gemini\tmp\free-claude-code`: Contains temporary tool outputs, heap snapshots, and logs.

## Assumptions (temporary)

*   The user wants to clear everything except essential project files.
*   The `C:\Users\Admin\.gemini\tmp\free-claude-code` directory contains files that are safe to remove.

## Open Questions

*   Should I delete all session files in `.scratch\sessions` or just those older than a certain date?
*   Should I clear all temporary tool outputs in `C:\Users\Admin\.gemini\tmp\free-claude-code`?

## Requirements

*   [ ] Clear `.pytest_cache`
*   [ ] Clear `.scratch\sessions`
*   [ ] Clear `C:\Users\Admin\.gemini\tmp\free-claude-code`

## Acceptance Criteria

* [ ] Specified directories/files are removed.
* [ ] No essential files or logs are deleted unintentionally.

## Definition of Done (team quality bar)

*   Cleanup script/commands executed.
*   Verify cleanup success.

## Out of Scope (explicit)

*   Deleting actual project source code.
*   Deleting recent logs if deemed necessary for debugging.

## Technical Notes

*   `.pytest_cache` contains pytest cache.
*   `.scratch\sessions` contains JSON session files.
*   `C:\Users\Admin\.gemini\tmp\free-claude-code` contains heap snapshots and temporary logs.
