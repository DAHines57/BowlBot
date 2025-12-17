# Bowling League Database Schema

Based on the Excel structure, here's a recommended normalized database schema for converting to a relational database.

## Core Tables

### 1. **players**
Master list of all players across all seasons.

```sql
CREATE TABLE players (
    player_id INT PRIMARY KEY AUTO_INCREMENT,
    player_name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_player_name (player_name)
);
```

**Fields:**
- `player_id` - Unique identifier
- `player_name` - Full name (e.g., "Dylan Hines", "John Torina")
- Timestamps for tracking

**Why:** Centralizes player data, prevents duplicates, allows tracking players across seasons.

---

### 2. **seasons**
List of all seasons.

```sql
CREATE TABLE seasons (
    season_id INT PRIMARY KEY AUTO_INCREMENT,
    season_number INT NOT NULL UNIQUE,
    season_name VARCHAR(50) NOT NULL,  -- e.g., "Season 10"
    start_date DATE,
    end_date DATE,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Fields:**
- `season_number` - Numeric identifier (1, 2, 3, etc.)
- `season_name` - Display name ("Season 10")
- `is_active` - Current/active season flag

---

### 3. **teams**
Teams per season (teams can have different names across seasons).

```sql
CREATE TABLE teams (
    team_id INT PRIMARY KEY AUTO_INCREMENT,
    season_id INT NOT NULL,
    team_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (season_id) REFERENCES seasons(season_id),
    UNIQUE KEY unique_team_season (season_id, team_name),
    INDEX idx_season (season_id),
    INDEX idx_team_name (team_name)
);
```

**Fields:**
- `team_name` - Team name for that season
- `season_id` - Which season this team belongs to

**Why:** Teams can change names/rosters between seasons, so team+season is the natural key.

---

### 4. **team_players** (Junction Table)
Many-to-many relationship: which players are on which teams in which seasons.

```sql
CREATE TABLE team_players (
    team_player_id INT PRIMARY KEY AUTO_INCREMENT,
    team_id INT NOT NULL,
    player_id INT NOT NULL,
    season_id INT NOT NULL,
    is_captain BOOLEAN DEFAULT FALSE,
    draft_round INT,  -- If you want to track draft info
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (season_id) REFERENCES seasons(season_id),
    UNIQUE KEY unique_player_team_season (player_id, team_id, season_id),
    INDEX idx_team (team_id),
    INDEX idx_player (player_id),
    INDEX idx_season (season_id)
);
```

**Fields:**
- Links players to teams for specific seasons
- `is_captain` - Track team captains
- `draft_round` - Optional draft information

**Why:** A player can be on different teams in different seasons. This normalizes that relationship.

---

### 5. **games**
Individual game scores (one row per game).

```sql
CREATE TABLE games (
    game_id INT PRIMARY KEY AUTO_INCREMENT,
    player_id INT NOT NULL,
    team_id INT NOT NULL,
    season_id INT NOT NULL,
    week_number INT NOT NULL,
    score INT NOT NULL CHECK (score >= 0 AND score <= 300),
    game_date DATE,
    is_playoff BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    FOREIGN KEY (season_id) REFERENCES seasons(season_id),
    UNIQUE KEY unique_player_week_season (player_id, week_number, season_id),
    INDEX idx_player_season (player_id, season_id),
    INDEX idx_team_season (team_id, season_id),
    INDEX idx_week (week_number, season_id)
);
```

**Fields:**
- `week_number` - Which week of the season
- `score` - The actual bowling score (0-300)
- `game_date` - Optional date tracking
- `is_playoff` - Distinguish regular season vs playoffs

**Why:** Normalizes scores into individual game records. Much easier to query and aggregate.

---

### 6. **team_standings**
Team statistics per season (can be calculated from games, but stored for performance).

```sql
CREATE TABLE team_standings (
    standing_id INT PRIMARY KEY AUTO_INCREMENT,
    team_id INT NOT NULL,
    season_id INT NOT NULL,
    wins INT DEFAULT 0,
    losses INT DEFAULT 0,
    ties INT DEFAULT 0,
    pins_for INT DEFAULT 0,
    pins_against INT DEFAULT 0,
    avg_per_game DECIMAL(5,2),
    avg_per_game_against DECIMAL(5,2),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    FOREIGN KEY (season_id) REFERENCES seasons(season_id),
    UNIQUE KEY unique_team_season_standing (team_id, season_id),
    INDEX idx_season (season_id)
);
```

**Fields:**
- All team statistics
- Can be recalculated from `games` table, but stored for quick access

**Why:** Pre-computed standings for fast queries. Can be updated via triggers or scheduled jobs.

---

### 7. **season_champions** (Optional)
Track season winners.

```sql
CREATE TABLE season_champions (
    champion_id INT PRIMARY KEY AUTO_INCREMENT,
    season_id INT NOT NULL,
    team_id INT NOT NULL,
    FOREIGN KEY (season_id) REFERENCES seasons(season_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    UNIQUE KEY unique_season_champion (season_id)
);
```

---

## Optional/Additional Tables

### 8. **draft_results** (If you want to track draft history)
```sql
CREATE TABLE draft_results (
    draft_id INT PRIMARY KEY AUTO_INCREMENT,
    season_id INT NOT NULL,
    captain_player_id INT NOT NULL,  -- Who is the captain
    drafted_player_id INT NOT NULL,  -- Who was drafted
    draft_round INT NOT NULL,
    pick_number INT NOT NULL,
    FOREIGN KEY (season_id) REFERENCES seasons(season_id),
    FOREIGN KEY (captain_player_id) REFERENCES players(player_id),
    FOREIGN KEY (drafted_player_id) REFERENCES players(player_id)
);
```

### 9. **player_averages** (Pre-computed, optional)
```sql
CREATE TABLE player_averages (
    average_id INT PRIMARY KEY AUTO_INCREMENT,
    player_id INT NOT NULL,
    season_id INT NOT NULL,
    games_played INT DEFAULT 0,
    total_pins INT DEFAULT 0,
    average DECIMAL(5,2),
    high_game INT,
    low_game INT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (season_id) REFERENCES seasons(season_id),
    UNIQUE KEY unique_player_season_avg (player_id, season_id)
);
```

---

## Key Relationships

```
seasons (1) ──< (many) teams
seasons (1) ──< (many) games
players (1) ──< (many) team_players ──> (many) teams
players (1) ──< (many) games
teams (1) ──< (many) games
teams (1) ──< (1) team_standings
```

---

## Example Queries

### Get all players for a team in a season:
```sql
SELECT p.player_name
FROM players p
JOIN team_players tp ON p.player_id = tp.player_id
JOIN teams t ON tp.team_id = t.team_id
WHERE t.team_name = 'Rolling Stoned' 
  AND t.season_id = (SELECT season_id FROM seasons WHERE season_number = 10);
```

### Get player's scores for a season:
```sql
SELECT week_number, score
FROM games
WHERE player_id = (SELECT player_id FROM players WHERE player_name = 'Dylan Hines')
  AND season_id = (SELECT season_id FROM seasons WHERE season_number = 10)
ORDER BY week_number;
```

### Get team standings:
```sql
SELECT t.team_name, ts.wins, ts.losses, ts.avg_per_game
FROM team_standings ts
JOIN teams t ON ts.team_id = t.team_id
WHERE ts.season_id = (SELECT season_id FROM seasons WHERE season_number = 10)
ORDER BY ts.wins DESC, ts.avg_per_game DESC;
```

### Calculate player average (if not pre-computed):
```sql
SELECT 
    p.player_name,
    COUNT(g.game_id) as games_played,
    AVG(g.score) as average,
    SUM(g.score) as total_pins
FROM players p
JOIN games g ON p.player_id = g.player_id
WHERE g.season_id = (SELECT season_id FROM seasons WHERE season_number = 10)
GROUP BY p.player_id, p.player_name;
```

---

## Migration Strategy

1. **Extract players** - Create unique list from all seasons
2. **Create seasons** - One row per season sheet
3. **Extract teams** - Per season
4. **Create team_players** - Link players to teams per season
5. **Extract games** - Convert week columns to individual game rows
6. **Calculate standings** - Aggregate from games or copy from Excel
7. **Add champions** - From Champs sheet

---

## Benefits of This Schema

✅ **Normalized** - No data duplication  
✅ **Scalable** - Easy to add new seasons/players  
✅ **Queryable** - Complex queries are straightforward  
✅ **Flexible** - Easy to add features (playoffs, tournaments, etc.)  
✅ **Maintainable** - Clear relationships and constraints  
✅ **Performance** - Indexes on common query paths  

---

## Alternative: Simpler Schema (If you want less normalization)

If you want something simpler for a small league:

1. **players** - Same as above
2. **seasons** - Same as above  
3. **player_scores** - Flattened: `(player_id, season_id, week_1, week_2, ..., week_N)`
4. **team_standings** - Same as above

But the normalized approach above is recommended for flexibility and data integrity.

