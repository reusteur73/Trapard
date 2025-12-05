CREATE TABLE Trapardeur (
    id INTEGER PRIMARY KEY,
    userId TEXT NOT NULL,
    vocalTime INTEGER,
    messageSent INTEGER,
    commandSent INTEGER
);
CREATE TABLE rappels (
        id INTEGER PRIMARY KEY,
        timestamp INTEGER NOT NULL,
        texte TEXT NOT NULL,
        auteur INTEGER NOT NULL,
        notified INTEGER NOT NULL,
        channel INTEGER NOT NULL
    , created_at INTEGER);
CREATE TABLE SongPlayedCount (
    id INTEGER PRIMARY KEY,
    songName TEXT NOT NULL,
    count INTEGER NOT NULL
);
CREATE TABLE FavSongs (
    id INTEGER PRIMARY KEY,
    userId TEXT NOT NULL,
    songName TEXT NOT NULL,
    count INTEGER NOT NULL
);
CREATE TABLE SkippedSongs (
    id INTEGER PRIMARY KEY,
    userId TEXT NOT NULL,
    songName TEXT NOT NULL,
    count INTEGER NOT NULL
);
CREATE TABLE cringedex (
    id INTEGER PRIMARY KEY,
    userId TEXT NOT NULL,
    cringeList JSON NOT NULL
);
CREATE TABLE LoLGamesTracker (
    id INTEGER PRIMARY KEY,
    userId TEXT NOT NULL,
    ign TEXT NOT NULL,
    puuid TEXT NOT NULL,
    region TEXT NOT NULL
, last_game_id TEXT NOT NULL DEFAULT '0', champions_mastery TEXT DEFAULT '{}');

UPDATE LoLGamesTracker SET last_game_id = '0' WHERE puuid = 'NA';

CREATE TABLE LikedSongs (
    id INTEGER PRIMARY KEY,
    userId TEXT NOT NULL,
    songName TEXT NOT NULL
);
CREATE TABLE cpasbien (
    id INTEGER PRIMARY KEY,
    title_name TEXT NOT NULL
);
CREATE TABLE PATCH_NOTES (
    game TEXT NOT NULL,
    value TEXT NOT NULL
);
CREATE TABLE musiques (
    id INTEGER PRIMARY KEY,
    pos INTEGER,
    duree INTEGER,
    name TEXT,
    artiste TEXT,
    downloader INTEGER
);
CREATE TABLE soundboard (
    id INTEGER PRIMARY KEY,
    name TEXT,
    downloader INTEGER
, duration INTEGER);
CREATE TABLE songs_stats (
    id INTEGER PRIMARY KEY,
    time INTEGER,
    number INTEGER
);
CREATE TABLE trapcoins (
    id INTEGER PRIMARY KEY,
    userid INTEGER,
    trapcoins INTEGER,
    epargne INTEGER
);
CREATE TABLE d_claim_streak (
    id INTEGER PRIMARY KEY,
    userid INTEGER,
    streak INTEGER,
    timestamp INTEGER
);
CREATE TABLE quizz_ladder (
    id INTEGER PRIMARY KEY,
    userid INTEGER,
    points INTEGER
);
CREATE TABLE type_racer_ladder(
    id INTEGER PRIMARY KEY,
    userid INTEGER,
    points INTEGER
);
CREATE TABLE devinette_ladder(
    id INTEGER PRIMARY KEY,
    userid INTEGER,
    points INTEGER,
    games_played INTEGER
);
CREATE TABLE sudoku_ladder(
    id INTEGER PRIMARY KEY,
    userid INTEGER,
    points INTEGER,
    easy INTEGER,
    medium INTEGER,
    hard INTEGER,
    insane INTEGER,
    temps INTEGER
);
CREATE TABLE mots_mels_ladder(
    id INTEGER PRIMARY KEY,
    userid INTEGER,
    points INTEGER,
    temps INTEGER
);
CREATE TABLE interets(
    id INTEGER PRIMARY KEY,
    userid INTEGER,
    tier INTEGER
);
CREATE TABLE rencontresNC (
    id INTEGER PRIMARY KEY,
    annonce_id INTEGER,
    category TEXT,
    titre TEXT,
    texte TEXT
);
CREATE TABLE musiquesV2 (id INTEGER PRIMARY KEY, pos INTEGER, duree INTEGER, name TEXT, artiste TEXT, downloader INTEGER, thumbnail TEXT, channel_avatar TEXT, likes INTEGER, views INTEGER, video_id TEXT);
CREATE TABLE musiquesV3 (
    id INTEGER PRIMARY KEY,
    pos INTEGER,
    duree INTEGER,
    name TEXT,
    artiste TEXT,
    downloader INTEGER,
    thumbnail TEXT,
    channel_avatar TEXT,
    likes INTEGER,
    views INTEGER,
    video_id TEXT
);
CREATE TABLE LikedSongsV2 (
    id INTEGER PRIMARY KEY,
    userId INTEGER NOT NULL,
    songId TEXT NOT NULL,
    songName TEXT NOT NULL
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE lol_match_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE Annonces_nc_Informatique (
    id INTEGER PRIMARY KEY,
    annonce_id INTEGER,
    user_id INTEGER,
    titre TEXT,
    texte TEXT,
    medias TEXT,
    created_at INTEGER
);
CREATE TABLE autoplay (
    id INTEGER PRIMARY KEY,
    pos INTEGER,
    duree INTEGER,
    name TEXT,
    artiste TEXT,
    downloader INTEGER,
    thumbnail TEXT,
    channel_avatar TEXT,
    likes INTEGER,
    views INTEGER,
    video_id TEXT
);