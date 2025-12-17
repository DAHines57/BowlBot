# Migration Guide: Excel to Database Structure

This guide explains how to migrate your existing Excel data into the new database-like structure, especially handling older seasons without individual game data.

## Overview

The new Excel structure (`Bowling_League_Database.xlsx`) has **9 sheets**:

1. **README** - Instructions and overview
2. **players** - Master player list
3. **seasons** - Season information
4. **teams** - Teams per season
5. **team_players** - Player-team relationships
6. **games** - Individual game scores (for detailed seasons)
7. **team_standings** - Team statistics
8. **player_aggregates** - For seasons without individual games
9. **season_champions** - Season winners

## Handling Older Seasons (No Individual Games)

### Option 1: Use `player_aggregates` Sheet (Recommended)

For seasons where you only have:
- Total games played
- Total pins
- Average score
- Maybe some week scores (but not all)

**Use the `player_aggregates` sheet:**

```
aggregate_id | player_id | team_id | season_id | total_games | total_pins | average | high_game | low_game | week_1 | week_2 | ... | notes
```

**Example:**
- Player: Dylan Hines
- Season: Season 3
- Total games: 28
- Total pins: 4900
- Average: 175.0
- High game: 220
- Low game: 120
- Week scores: 180, 185, 170, 190, 175, 180, 185 (if available)

### Option 2: Partial Games Data

If you have some week scores but not all:
- Fill in the weeks you have in `player_aggregates`
- Leave missing weeks blank
- Calculate `total_games` and `total_pins` from available data
- Note in the `notes` column: "Partial data - weeks 1-7 only"

### Option 3: Team-Level Data Only

If you only have team standings:
- Use `team_standings` sheet
- Use `player_aggregates` with minimal data:
  - `total_games`: Estimate or leave blank
  - `average`: If you have it, otherwise calculate from available data
  - `notes`: "Team-level data only - individual games not available"

## Step-by-Step Migration

### Step 1: Extract Players

From your old Excel, go through all season sheets and create a unique list:

1. Open `players` sheet
2. List all unique player names
3. Assign sequential `player_id` (1, 2, 3, ...)
4. Fill in `player_name`

**Tip:** Use Excel's "Remove Duplicates" feature on a temporary list first.

### Step 2: Create Seasons

1. Open `seasons` sheet
2. For each season in your old Excel:
   - `season_number`: 1, 2, 3, etc.
   - `season_name`: "Season 1", "Season 2", etc.
   - `is_active`: TRUE for current season, FALSE for others

### Step 3: Extract Teams

1. Open `teams` sheet
2. For each season, list all teams:
   - `team_id`: Sequential (can restart per season or be global)
   - `season_id`: Link to seasons sheet
   - `team_name`: Team name from that season

### Step 4: Link Players to Teams

1. Open `team_players` sheet
2. For each player in each season:
   - `team_id`: Which team they were on
   - `player_id`: Which player
   - `season_id`: Which season
   - `is_captain`: TRUE if they were captain

### Step 5: Handle Game Data

#### For Seasons WITH Individual Games (Season 10+):

1. Open `games` sheet
2. For each player's week score:
   - Create one row per game
   - `player_id`, `team_id`, `season_id`
   - `week_number`: 1, 2, 3, etc.
   - `score`: The actual score
   - `game_date`: If available

**Example:**
```
Dylan Hines, Week 1, Score 180 → games row
Dylan Hines, Week 2, Score 195 → games row
Dylan Hines, Week 3, Score 170 → games row
```

#### For Seasons WITHOUT Individual Games (Season 1-9):

1. Open `player_aggregates` sheet
2. For each player in that season:
   - `player_id`, `team_id`, `season_id`
   - `total_games`: Total games played (if known)
   - `total_pins`: Total pins (if known)
   - `average`: Average score (if known)
   - `high_game`, `low_game`: If available
   - `week_1` through `week_7`: Fill in if you have week data
   - `notes`: "Aggregated data - individual games not available"

**Example:**
```
aggregate_id: 1
player_id: 5 (Dylan Hines)
team_id: 3
season_id: 3
total_games: 28
total_pins: 4900
average: 175.0
high_game: 220
low_game: 120
week_1: 180
week_2: 185
week_3: 170
...
notes: "Season 3 - aggregated data only"
```

### Step 6: Team Standings

1. Open `team_standings` sheet
2. Copy standings from old Excel:
   - `team_id`, `season_id`
   - `wins`, `losses`, `ties`
   - `pins_for`, `pins_against`
   - `avg_per_game`, `avg_per_game_against`

### Step 7: Season Champions

1. Open `season_champions` sheet
2. From your "Champs" sheet:
   - `season_id`
   - `team_id` (find the team_id from teams sheet)
   - `notes`: Team name for reference

## Data Quality Tips

### Handling Missing Data

- **Missing scores:** Leave blank (don't use 0 unless it was actually a 0 score)
- **Unknown totals:** Leave blank or use `notes` column to explain
- **Partial data:** Always note in `notes` column what's missing

### Consistency

- **Player names:** Use exact same spelling everywhere
- **Team names:** Match exactly between sheets
- **IDs:** Keep sequential, don't skip numbers (easier to maintain)

### Validation

- **Score range:** 0-300 (validate this)
- **Week numbers:** Should be sequential (1, 2, 3, ...)
- **Foreign keys:** Make sure `player_id`, `team_id`, `season_id` exist in their respective sheets

## Example: Migrating Season 3 (Old Data)

**Old Excel has:**
- Team standings with wins/losses
- Player averages
- Some week scores but not all

**New Structure:**

1. **players sheet:** Add all players from Season 3
2. **seasons sheet:** Add Season 3 entry
3. **teams sheet:** Add all teams from Season 3
4. **team_players sheet:** Link players to teams
5. **player_aggregates sheet:** 
   - For each player, enter:
     - Known averages
     - Available week scores
     - Total games if known
     - Note: "Season 3 - partial data"
6. **team_standings sheet:** Copy standings
7. **games sheet:** Leave empty (no individual games)

## Querying the Data

### Get all players for a team:
```
Filter team_players where team_id = X and season_id = Y
Join with players to get names
```

### Get player's season stats:
```
If season has games: Sum from games sheet
If season is aggregated: Use player_aggregates sheet
```

### Calculate averages:
```
For games: AVG(score) GROUP BY player_id, season_id
For aggregates: Use average column directly
```

## Benefits of This Structure

✅ **Flexible:** Handles both detailed and aggregated data  
✅ **Scalable:** Easy to add new seasons  
✅ **Queryable:** Can use Excel filters, pivot tables, or export to SQL  
✅ **Maintainable:** Clear separation of concerns  
✅ **Complete:** Preserves all historical data, even if incomplete  

## Next Steps

1. Start with current season (most complete data)
2. Work backwards through seasons
3. Fill in what you have, note what's missing
4. Consider exporting to SQL database later if needed

