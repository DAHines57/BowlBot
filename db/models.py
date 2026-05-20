from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    sheet_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    sort_order: Mapped[Optional[int]] = mapped_column(Integer)

    teams: Mapped[list["Team"]] = relationship(
        back_populates="season", cascade="all, delete-orphan"
    )
    roster_members: Mapped[list["TeamRosterMember"]] = relationship(
        back_populates="season", cascade="all, delete-orphan"
    )
    player_weeks: Mapped[list["PlayerWeek"]] = relationship(
        back_populates="season", cascade="all, delete-orphan"
    )
    matchup_overrides: Mapped[list["MatchupOverride"]] = relationship(
        back_populates="season", cascade="all, delete-orphan"
    )


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("season_id", "name", name="uq_teams_season_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    color_hex: Mapped[Optional[str]] = mapped_column(String(7))

    season: Mapped["Season"] = relationship(back_populates="teams")
    roster_members: Mapped[list["TeamRosterMember"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )
    player_weeks: Mapped[list["PlayerWeek"]] = relationship(back_populates="team")


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    roster_members: Mapped[list["TeamRosterMember"]] = relationship(back_populates="player")
    player_weeks: Mapped[list["PlayerWeek"]] = relationship(back_populates="player")


class TeamRosterMember(Base):
    __tablename__ = "team_roster_members"
    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "team_id",
            "player_id",
            name="uq_roster_season_team_player",
        ),
        Index("ix_roster_members_season_team", "season_id", "team_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    is_captain: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    started_week: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    ended_week: Mapped[Optional[int]] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    season: Mapped["Season"] = relationship(back_populates="roster_members")
    team: Mapped["Team"] = relationship(back_populates="roster_members")
    player: Mapped["Player"] = relationship(back_populates="roster_members")


class PlayerWeek(Base):
    __tablename__ = "player_weeks"
    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "week",
            "team_id",
            "player_display_name",
            name="uq_player_weeks_season_week_team_player",
        ),
        Index("ix_player_weeks_season_week", "season_id", "week"),
        Index("ix_player_weeks_season_player", "season_id", "player_id"),
        Index(
            "ix_player_weeks_season_week_present",
            "season_id",
            "week",
            postgresql_where=text("absent IS FALSE"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[Optional[int]] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"))
    player_display_name: Mapped[str] = mapped_column(String(128), nullable=False)

    game1: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    game2: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    game3: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    game4: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    game5: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    week_average: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))

    absent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    substitute: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    playoffs: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    opponent: Mapped[Optional[str]] = mapped_column(Text)

    source_row_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    season: Mapped["Season"] = relationship(back_populates="player_weeks")
    team: Mapped["Team"] = relationship(back_populates="player_weeks")
    player: Mapped[Optional["Player"]] = relationship(back_populates="player_weeks")


class MatchupOverride(Base):
    __tablename__ = "matchup_overrides"
    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "week",
            "team",
            name="uq_matchup_overrides_season_week_team",
        ),
        Index("ix_matchup_overrides_season_week", "season_id", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    team: Mapped[str] = mapped_column(String(128), nullable=False)
    opponent: Mapped[str] = mapped_column(String(128), nullable=False)
    wins: Mapped[int] = mapped_column(Integer, nullable=False)
    losses: Mapped[int] = mapped_column(Integer, nullable=False)
    ties: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    playoffs: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    season: Mapped["Season"] = relationship(back_populates="matchup_overrides")
