# Migration Script Usage

## Quick Start

Run the migration script to convert your old Excel file to the new database structure:

```bash
python migrate_to_database.py
```

Or specify which season starts having detailed individual games:

```bash
python migrate_to_database.py 9
```

This will use Season 9+ for individual games, and Season 1-8 as aggregates.

## What It Does

The migration script:

1. ✅ **Extracts all unique players** from all seasons
2. ✅ **Creates season entries** for each season sheet
3. ✅ **Extracts teams** per season
4. ✅ **Links players to teams** (team_players junction table)
5. ✅ **Migrates game data:**
   - **Detailed seasons** (default: Season 10+): Creates individual game rows in `games` sheet
   - **Older seasons** (default: Season 1-9): Creates aggregate records in `player_aggregates` sheet
6. ✅ **Migrates team standings** with wins, losses, pins, averages
7. ✅ **Migrates season champions** from Champs sheet

## Output

Creates: `Bowling_League_Database_Migrated.xlsx`

This is a copy of the template with all your data migrated into it.

## Customization

### Change Which Seasons Have Detailed Games

Edit the script or pass as argument:

```python
# In the script, change:
detailed_start = 10  # Season 10+ will have individual games

# Or pass as command line argument:
python migrate_to_database.py 8  # Season 8+ will have individual games
```

### Adjust Data Extraction

The script looks for:
- **Teams**: Column B, rows 2-15 (standings section)
- **Players**: Column C, rows 13+ (player scores section)
- **Scores**: Columns 4+ (Week 1, Week 2, etc.)

If your Excel structure is different, adjust the row/column numbers in the script.

## After Migration

1. **Review the migrated file** - Check that data looks correct
2. **Verify player counts** - Make sure all players were found
3. **Check aggregates** - Review older seasons in `player_aggregates` sheet
4. **Validate games** - Check that detailed seasons have individual game rows
5. **Update manually** - Add any missing data or corrections

## Troubleshooting

### "File not found"
- Make sure `Bowling- Friends League v4.xlsx` is in the same directory
- Make sure `Bowling_League_Database.xlsx` (template) exists

### Missing players or teams
- The script extracts from player scores section (row 13+)
- Check if your Excel has players in a different location
- Manually add missing entries after migration

### Scores not migrating
- Check if scores are in columns 4+ (Week columns)
- Verify scores are numeric values, not formulas
- Older seasons might only have aggregates (this is expected)

### Team linking issues
- Teams are matched by name
- If team names changed between seasons, they'll be separate entries
- This is correct behavior - teams can change names

## Next Steps

After migration:
1. Use the new database structure for your bot
2. Update `sheets_handler.py` to read from new structure
3. Or export to SQL database if needed

