<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2025-01-27 | Updated: 2025-01-27 -->

# scripts

## Purpose
Utility scripts for development, testing, and maintenance of the trading bot system.

## Key Files

| File | Description |
|------|-------------|
| (To be documented) | Utility scripts for various operations |

**Note**: The scripts directory contents need to be catalogued. Common scripts might include:
- Database migration scripts
- Data export/import utilities
- Testing helpers
- Deployment scripts
- Maintenance tools

## For AI Agents

### Working In This Directory
- Scripts are typically standalone utilities
- They may require specific environment configurations
- Always check script dependencies before execution
- Test scripts in development environment first

### Common Script Patterns

```python
#!/usr/bin/env python3
"""
Script description
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_config
# ... rest of script
```

### Adding New Scripts
1. Make script executable: `chmod +x script_name.py`
2. Add shebang line: `#!/usr/bin/env python3`
3. Include docstring with usage instructions
4. Add command-line argument parsing if needed
5. Update this AGENTS.md with script description

## Dependencies

### Internal
- `feature_source/` - Main bot code
- `src/` - Legacy utilities (if needed)

### External
- Varies by script purpose

## Common Use Cases

### Database Maintenance
```bash
# Backup PnL database
./scripts/backup_db.py

# Migrate database schema
./scripts/migrate_db.py --version 2
```

### Data Export
```bash
# Export trade history
./scripts/export_trades.py --wallet wallet_0 --format csv

# Export portfolio snapshots
./scripts/export_portfolio.py --days 30
```

### Testing
```bash
# Run strategy backtest
./scripts/backtest.py --strategy arbitrage --start 2024-01-01

# Test API connections
./scripts/test_connections.py
```

<!-- MANUAL: Add specific script descriptions below -->
