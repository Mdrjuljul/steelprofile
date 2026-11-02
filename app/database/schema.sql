-- ============================================================================
--  SteelProfile — schéma SQLite du catalogue (Phase 1)
--  Toutes les longueurs sont en millimètres (mm). Voir docs/catalogue.md.
--
--  Principes :
--   * une ligne = une géométrie primaire documentée (jamais une valeur calculée) ;
--   * une valeur absente reste NULL — elle n'est jamais remplacée par défaut ;
--   * la provenance de chaque valeur est enregistrée (table, règle de série) ;
--   * les propriétés de section (A, I, W…) sont dérivées, donc stockées à part
--     et marquées comme non indépendantes.
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Référentiels
-- ---------------------------------------------------------------------------

-- Source documentaire (dépôt, site, norme) : traçabilité et licence.
CREATE TABLE source (
    source_id       TEXT PRIMARY KEY,          -- 'ssdb-github', 'en-10365'
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL              -- 'repository' | 'website' | 'standard' | 'manufacturer'
                    CHECK (kind IN ('repository','website','standard','manufacturer','dataset')),
    url             TEXT,
    retrieved_on    TEXT,                      -- ISO 8601 (date de collecte)
    version         TEXT,                      -- tag / commit / édition
    license         TEXT,                      -- identifiant SPDX ou libellé exact
    license_url     TEXT,
    redistribution  TEXT NOT NULL              -- 'allowed' | 'restricted' | 'unknown' | 'not_applicable'
                    CHECK (redistribution IN ('allowed','restricted','unknown','not_applicable')),
    usage           TEXT NOT NULL              -- 'data_source' | 'reference_only' | 'rejected' | 'local_only'
                    CHECK (usage IN ('data_source','reference_only','rejected','local_only')),
    notes           TEXT
);

-- Norme de référence. `verified` = les valeurs du catalogue ont-elles été
-- contrôlées ligne à ligne contre une copie licite de la norme ?
CREATE TABLE standard (
    standard_id     TEXT PRIMARY KEY,          -- 'EN 10365:2017'
    code            TEXT NOT NULL,             -- 'EN 10365'
    edition         TEXT,                      -- '2017'
    title           TEXT,
    status          TEXT                       -- 'current' | 'superseded' | 'assumed' | 'mixed'
                    CHECK (status IN ('current','superseded','assumed','mixed')),
    superseded_by   TEXT REFERENCES standard(standard_id),
    verified        INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0,1)),
    notes           TEXT
);

-- Famille fonctionnelle du cahier des charges (§3).
CREATE TABLE family (
    family_id       TEXT PRIMARY KEY,          -- 'I', 'H', 'U', 'L', 'T', 'HOLLOW', 'SOLID'
    label_fr        TEXT NOT NULL,
    spec_section    TEXT,                      -- '3.1' … '3.7'
    expected        INTEGER NOT NULL DEFAULT 1,-- famille attendue au périmètre
    sort_order      INTEGER NOT NULL DEFAULT 0
);

-- Série normalisée = un fichier de données (IPE, HEA, SHS-HF, …).
CREATE TABLE series (
    series_id       TEXT PRIMARY KEY,          -- 'IPE', 'SHS-HF'
    family_id       TEXT NOT NULL REFERENCES family(family_id),
    label           TEXT NOT NULL,
    shape_id        TEXT NOT NULL REFERENCES shape(shape_id),
    standard_id     TEXT REFERENCES standard(standard_id),
    category        TEXT NOT NULL DEFAULT 'standard'
                    CHECK (category IN ('standard','commercial')),  -- §3.7 : jamais confondues
    commercial_ref  TEXT,                      -- programme + édition, pour une série commerciale
    process         TEXT                       -- 'hot_rolled' | 'hot_finished' | 'cold_formed'
                    CHECK (process IN ('hot_rolled','hot_finished','cold_formed')),
    corner_radii_rule TEXT REFERENCES corner_radius_rule(rule_id),
    source_id       TEXT NOT NULL REFERENCES source(source_id),
    source_ref      TEXT,                      -- chemin du fichier d'origine
    alias_patterns  TEXT,                      -- JSON : motifs de désignation alternatifs
    notes           TEXT
);

-- Forme géométrique = jeu de paramètres + générateur (Phase 2).
CREATE TABLE shape (
    shape_id        TEXT PRIMARY KEY,          -- 'I', 'I_TAPERED', 'U', 'U_TAPERED', 'SHS',
                                               -- 'RHS', 'CHS', 'L_EQ', 'L', 'FLAT',
                                               -- 'T_TAPERED', 'ROUND', 'SQUARE'
    label_fr        TEXT NOT NULL,
    symmetric_y     INTEGER NOT NULL CHECK (symmetric_y IN (0,1)),
    generator       TEXT,                      -- module Python prévu (Phase 2)
    notes           TEXT
);

-- Paramètres exigés par chaque forme. `required = 1` : sans lui, pas de
-- reconstruction exacte possible (statut 'incomplete').
CREATE TABLE param_def (
    shape_id        TEXT NOT NULL REFERENCES shape(shape_id),
    param           TEXT NOT NULL,             -- 'h','b','tw','tf','t','r','r1','r2','ro','ri','D','a','slope_pct','x_tf'
    unit            TEXT NOT NULL DEFAULT 'mm',
    required        INTEGER NOT NULL CHECK (required IN (0,1)),
    label_fr        TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (shape_id, param)
);

-- Règle de rayon d'angle des profilés creux (EN 10210-2 / EN 10219-2),
-- découpée en bandes d'épaisseur.
CREATE TABLE corner_radius_rule (
    rule_id         TEXT PRIMARY KEY,          -- 'EN10210-2', 'EN10219-2'
    process         TEXT NOT NULL,
    standard_ref    TEXT,
    note            TEXT
);

-- Une bande par domaine d'épaisseur : ro = ro_factor · t, ri = ri_factor · t.
CREATE TABLE corner_radius_band (
    band_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id         TEXT NOT NULL REFERENCES corner_radius_rule(rule_id),
    t_min           REAL,                      -- borne inférieure exclue (mm), NULL = -inf
    t_max           REAL,                      -- borne supérieure incluse (mm), NULL = +inf
    ro_factor       REAL NOT NULL,
    ri_factor       REAL NOT NULL,
    note            TEXT
);

-- ---------------------------------------------------------------------------
-- Catalogue
-- ---------------------------------------------------------------------------

CREATE TABLE profile (
    profile_id      TEXT PRIMARY KEY,          -- 'IPE/IPE 200' (série + désignation)
    series_id       TEXT NOT NULL REFERENCES series(series_id),
    designation     TEXT NOT NULL,             -- désignation canonique de la source
    designation_key TEXT NOT NULL,             -- clé de recherche normalisée (majuscules, sans espace)
    sort_key        REAL,                      -- tri « naturel » dans la série (h, b, t…)
    geometry_status TEXT NOT NULL              -- 'complete' | 'incomplete' | 'infeasible'
                    CHECK (geometry_status IN ('complete','incomplete','infeasible')),
    geometry_source TEXT NOT NULL              -- 'table' | 'table+rule' : rayons lus ou déduits d'une règle
                    CHECK (geometry_source IN ('table','table+rule')),
    verified        INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0,1)),
    verified_on     TEXT,                      -- date du contrôle (NULL = jamais contrôlé)
    unit            TEXT NOT NULL DEFAULT 'mm',
    source_row      TEXT,                      -- ligne du fichier d'origine
    notes           TEXT,
    UNIQUE (series_id, designation)
);

CREATE INDEX idx_profile_series ON profile(series_id);
CREATE INDEX idx_profile_key    ON profile(designation_key);

-- Géométrie primaire : une ligne par paramètre applicable à la forme.
-- value NULL = paramètre documenté mais absent de la source (jamais inventé).
CREATE TABLE profile_param (
    profile_id      TEXT NOT NULL REFERENCES profile(profile_id) ON DELETE CASCADE,
    param           TEXT NOT NULL,
    value           REAL,
    unit            TEXT NOT NULL DEFAULT 'mm',
    origin          TEXT NOT NULL              -- 'table' | 'series_rule' | 'printed_override'
                    CHECK (origin IN ('table','series_rule','printed_override')),
    note            TEXT,
    PRIMARY KEY (profile_id, param)
);

CREATE TABLE profile_alias (
    profile_id      TEXT NOT NULL REFERENCES profile(profile_id) ON DELETE CASCADE,
    alias           TEXT NOT NULL,
    alias_key       TEXT NOT NULL,
    PRIMARY KEY (profile_id, alias)
);

CREATE INDEX idx_alias_key ON profile_alias(alias_key);

-- Propriétés de section recopiées du dépôt (A, I, W, masse…).
-- Elles sont DÉRIVÉES de la même géométrie : elles ne valident donc pas le
-- modèle, elles servent de valeur de comparaison en Phase 2.
CREATE TABLE derived_property (
    profile_id      TEXT NOT NULL REFERENCES profile(profile_id) ON DELETE CASCADE,
    param           TEXT NOT NULL,             -- 'A','mass','Iy','Wpl_y'…
    value           REAL,                      -- NULL si non publiée
    unit            TEXT,
    status          TEXT NOT NULL DEFAULT 'supported'
                    CHECK (status IN ('supported','unsupported')),
    method          TEXT,                      -- méthode déclarée par la source
    independent     INTEGER NOT NULL DEFAULT 0,-- 0 = recalculée depuis la même géométrie
    PRIMARY KEY (profile_id, param)
);

-- Anomalies, manques et réserves : le rapport Phase 1 est généré d'ici.
CREATE TABLE catalog_issue (
    issue_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    scope           TEXT NOT NULL CHECK (scope IN ('source','series','profile','family')),
    ref             TEXT,                      -- series_id / profile_id / family_id
    severity        TEXT NOT NULL CHECK (severity IN ('info','warning','blocking')),
    code            TEXT NOT NULL,
    message         TEXT NOT NULL
);

CREATE INDEX idx_issue_scope ON catalog_issue(scope, ref);

-- ---------------------------------------------------------------------------
-- Vues
-- ---------------------------------------------------------------------------

-- Géométrie à plat (une colonne par paramètre) pour l'affichage et les tests.
CREATE VIEW v_profile_geometry AS
SELECT
    p.profile_id,
    p.series_id,
    s.family_id,
    p.designation,
    p.geometry_status,
    p.geometry_source,
    MAX(CASE WHEN pp.param = 'h'         THEN pp.value END) AS h,
    MAX(CASE WHEN pp.param = 'b'         THEN pp.value END) AS b,
    MAX(CASE WHEN pp.param = 'tw'        THEN pp.value END) AS tw,
    MAX(CASE WHEN pp.param = 'tf'        THEN pp.value END) AS tf,
    MAX(CASE WHEN pp.param = 't'         THEN pp.value END) AS t,
    MAX(CASE WHEN pp.param = 'r'         THEN pp.value END) AS r,
    MAX(CASE WHEN pp.param = 'r1'        THEN pp.value END) AS r1,
    MAX(CASE WHEN pp.param = 'r2'        THEN pp.value END) AS r2,
    MAX(CASE WHEN pp.param = 'ro'        THEN pp.value END) AS ro,
    MAX(CASE WHEN pp.param = 'ri'        THEN pp.value END) AS ri,
    MAX(CASE WHEN pp.param = 'D'         THEN pp.value END) AS "D",
    MAX(CASE WHEN pp.param = 'a'         THEN pp.value END) AS a,
    MAX(CASE WHEN pp.param = 'slope_pct' THEN pp.value END) AS slope_pct,
    MAX(CASE WHEN pp.param = 'x_tf'      THEN pp.value END) AS x_tf
FROM profile p
JOIN series s ON s.series_id = p.series_id
LEFT JOIN profile_param pp ON pp.profile_id = p.profile_id
GROUP BY p.profile_id;

-- Comptage par famille : références totales / exploitables / incomplètes.
CREATE VIEW v_family_stats AS
SELECT
    f.family_id,
    f.label_fr,
    (SELECT COUNT(*) FROM series se WHERE se.family_id = f.family_id) AS series_count,
    (SELECT COUNT(*) FROM profile p JOIN series se ON se.series_id = p.series_id
      WHERE se.family_id = f.family_id) AS profile_count,
    (SELECT COUNT(*) FROM profile p JOIN series se ON se.series_id = p.series_id
      WHERE se.family_id = f.family_id AND p.geometry_status = 'complete') AS profile_complete,
    (SELECT COUNT(*) FROM profile p JOIN series se ON se.series_id = p.series_id
      WHERE se.family_id = f.family_id AND p.geometry_status <> 'complete') AS profile_incomplete,
    (SELECT COUNT(*) FROM profile p JOIN series se ON se.series_id = p.series_id
      WHERE se.family_id = f.family_id AND p.geometry_source = 'table+rule') AS profile_rule_radii
FROM family f
ORDER BY f.sort_order;

-- Comptage par série.
CREATE VIEW v_series_stats AS
SELECT
    se.series_id,
    se.family_id,
    se.label,
    se.shape_id,
    se.process,
    st.standard_id,
    se.category,
    se.commercial_ref,
    (SELECT COUNT(*) FROM profile p WHERE p.series_id = se.series_id) AS profile_count,
    (SELECT COUNT(*) FROM profile p WHERE p.series_id = se.series_id
       AND p.geometry_status = 'complete') AS profile_complete,
    (SELECT COUNT(*) FROM profile p WHERE p.series_id = se.series_id
       AND p.geometry_source = 'table+rule') AS profile_rule_radii
FROM series se
LEFT JOIN standard st ON st.standard_id = se.standard_id
ORDER BY se.family_id, se.series_id;
