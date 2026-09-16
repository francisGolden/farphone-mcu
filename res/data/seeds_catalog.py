SEEDS_CATALOG = [
    {
        "id": "SEED_NOURISHMENT",
        "name": "Nourishment",
        "target_sec": 15 * 60,
        "bonus_base": 250,
        "accent_color": 0x5CD632,
        "pool": [
            # Common (60%)
            {"id": "FENNEL",        "name": "Finocchio",       "rarity": "COM", "xp_mul": 1.0},
            {"id": "ONION",         "name": "Cipolla",         "rarity": "COM", "xp_mul": 1.0},
            {"id": "GARLIC",        "name": "Aglio",           "rarity": "COM", "xp_mul": 1.0},
            {"id": "ROSEMARY",      "name": "Rosmarino",       "rarity": "COM", "xp_mul": 1.0},
            {"id": "SAGE",          "name": "Salvia",          "rarity": "COM", "xp_mul": 1.0},
            {"id": "DANDELION",     "name": "Tarassaco",       "rarity": "COM", "xp_mul": 1.0},
            {"id": "LEMON",         "name": "Limone",          "rarity": "COM", "xp_mul": 1.0},
            # Rare (30%)
            {"id": "LIME_TREE",     "name": "Tiglio",          "rarity": "RAR", "xp_mul": 1.5},
            {"id": "BLACK_PEPPER",  "name": "Pepe",            "rarity": "RAR", "xp_mul": 1.5},
            {"id": "CHILI_PEPPER",  "name": "Peperoncino",     "rarity": "RAR", "xp_mul": 1.5},
            {"id": "BOLDO",         "name": "Boldo",           "rarity": "RAR", "xp_mul": 1.5},
            {"id": "TURMERIC",      "name": "Curcuma",         "rarity": "RAR", "xp_mul": 1.6},
            # Legendary (10%)
            {"id": "LIQUORICE",     "name": "Liquirizia",      "rarity": "LEG", "xp_mul": 2.5},
            {"id": "STAR_ANISE",    "name": "Anice Stellato",  "rarity": "LEG", "xp_mul": 3.0}
        ]
    },
    {
        "id": "SEED_LEARNING",
        "name": "Learning",
        "target_sec": 45 * 60,
        "bonus_base": 600,
        "accent_color": 0x44AAFF,
        "pool": [
            # Common (60%)
            {"id": "WHEAT",         "name": "Grano",           "rarity": "COM", "xp_mul": 1.0},
            {"id": "RICE",          "name": "Riso",            "rarity": "COM", "xp_mul": 1.0},
            {"id": "BEAN",          "name": "Fagiolo",         "rarity": "COM", "xp_mul": 1.0},
            {"id": "CHICKPEA",      "name": "Cece",            "rarity": "COM", "xp_mul": 1.0},
            {"id": "MILLET",        "name": "Miglio",          "rarity": "COM", "xp_mul": 1.0},
            {"id": "SORGHUM",       "name": "Sorgo",           "rarity": "COM", "xp_mul": 1.0},
            {"id": "PUMPKIN",       "name": "Zucca",           "rarity": "COM", "xp_mul": 1.0},
            {"id": "SUNFLOWER",     "name": "Girasole",        "rarity": "COM", "xp_mul": 1.0},
            # Rare (30%)
            {"id": "WALNUT",        "name": "Noce",            "rarity": "RAR", "xp_mul": 1.5},
            {"id": "ALMOND",        "name": "Mandorla",        "rarity": "RAR", "xp_mul": 1.5},
            {"id": "FLAX",          "name": "Lino",            "rarity": "RAR", "xp_mul": 1.5},
            {"id": "CHIA",          "name": "Chia",            "rarity": "RAR", "xp_mul": 1.5},
            {"id": "GRASS_PEA",     "name": "Cicerchia",       "rarity": "RAR", "xp_mul": 1.5},
            {"id": "CHESTNUT",      "name": "Castagno",        "rarity": "RAR", "xp_mul": 1.6},
            {"id": "JUNIPER",       "name": "Ginepro",         "rarity": "RAR", "xp_mul": 1.6},
            {"id": "ROSE_HIP",      "name": "Rosa Canina",     "rarity": "RAR", "xp_mul": 1.6},
            {"id": "BLUEBERRY",     "name": "Mirtillo",        "rarity": "RAR", "xp_mul": 1.8},
            # Legendary (10%)
            {"id": "COFFEE",        "name": "Caffè",           "rarity": "LEG", "xp_mul": 2.5},
            {"id": "MORINGA",       "name": "Moringa",         "rarity": "LEG", "xp_mul": 2.6},
            {"id": "TOBACCO",       "name": "Tabacco",         "rarity": "LEG", "xp_mul": 2.8},
            {"id": "COCA",          "name": "Coca",            "rarity": "LEG", "xp_mul": 3.0}
        ]
    },
    {
        "id": "SEED_REST",
        "name": "Rest",
        "target_sec": 60 * 60,
        "bonus_base": 1200,
        "accent_color": 0x9955FF,
        "pool": [
            # Common (60%)
            {"id": "CHAMOMILE",      "name": "Camomilla",      "rarity": "COM", "xp_mul": 1.0},
            {"id": "MALLOW",         "name": "Malva",          "rarity": "COM", "xp_mul": 1.0},
            {"id": "MELISSA",        "name": "Melissa",        "rarity": "COM", "xp_mul": 1.0},
            {"id": "LIME_TREE",      "name": "Tiglio",         "rarity": "COM", "xp_mul": 1.0},
            # Rare (30%)
            {"id": "LAVENDER",       "name": "Lavanda",        "rarity": "RAR", "xp_mul": 1.5},
            {"id": "VALERIAN",       "name": "Valeriana",      "rarity": "RAR", "xp_mul": 1.5},
            {"id": "CORNFLOWER",     "name": "Fiordaliso",     "rarity": "RAR", "xp_mul": 1.5},
            {"id": "HOPS",           "name": "Luppolo",        "rarity": "RAR", "xp_mul": 1.7},
            # Legendary (10%)
            {"id": "PASSION_FLOWER", "name": "Passiflora",     "rarity": "LEG", "xp_mul": 2.5},
            {"id": "POPPY",          "name": "Papavero",       "rarity": "LEG", "xp_mul": 3.0}
        ]
    },
    {
        "id": "SEED_LABOUR",
        "name": "Labour",
        "target_sec": 30 * 60,
        "bonus_base": 500,
        "accent_color": 0xFFA500,
        "pool": [
            # Common (60%)
            {"id": "WHEAT",     "name": "Grano",               "rarity": "COM", "xp_mul": 1.0},
            {"id": "OAT",       "name": "Avena",               "rarity": "COM", "xp_mul": 1.0},
            {"id": "BARLEY",    "name": "Orzo",                "rarity": "COM", "xp_mul": 1.0},
            {"id": "ROSEMARY",  "name": "Rosmarino",           "rarity": "COM", "xp_mul": 1.0},
            {"id": "THYME",     "name": "Timo",                "rarity": "COM", "xp_mul": 1.0},
            # Rare (30%)
            {"id": "SPELT",     "name": "Farro",               "rarity": "RAR", "xp_mul": 1.5},
            {"id": "SAGE",      "name": "Salvia",              "rarity": "RAR", "xp_mul": 1.5},
            {"id": "WALNUT",    "name": "Noce",                "rarity": "RAR", "xp_mul": 1.5},
            {"id": "MORINGA",   "name": "Moringa",             "rarity": "RAR", "xp_mul": 1.7},
            # Legendary (10%)
            {"id": "OLIVE",     "name": "Ulivo",               "rarity": "LEG", "xp_mul": 2.5},
            {"id": "OAK",       "name": "Quercia",             "rarity": "LEG", "xp_mul": 3.0}
        ]
    },
    {
        "id": "SEED_RECREATION",
        "name": "Recreation",
        "target_sec": 60,  # Sprint 1 min
        "bonus_base": 100,
        "accent_color": 0xFF44AA,
        "pool": [
            # Common (60%)
            {"id": "AGRIMONY",          "name": "Agrimonia",    "rarity": "COM", "xp_mul": 1.0},
            {"id": "CLEMATIS",          "name": "Clematis",     "rarity": "COM", "xp_mul": 1.0},
            {"id": "HORNBEAM",          "name": "Carpino",      "rarity": "COM", "xp_mul": 1.0},
            # Rare (30%)
            {"id": "CRAB_APPLE",        "name": "Melo Selv.",   "rarity": "RAR", "xp_mul": 1.5},
            {"id": "IMPATIENS",         "name": "Balsamina",    "rarity": "RAR", "xp_mul": 1.5},
            {"id": "WEEPING_WILLOW",    "name": "Salice Piang.","rarity": "RAR", "xp_mul": 1.7},
            # Legendary (10%)
            {"id": "WHITE_CHESTNUT",    "name": "Castagno B.",  "rarity": "LEG", "xp_mul": 2.5},
            {"id": "STAR_OF_BETHLEHEM", "name": "St. Betlemme", "rarity": "LEG", "xp_mul": 3.0}
        ]
    },
    {
        "id": "SEED_ATTUNEMENT",
        "name": "Attunement",
        "target_sec": 20 * 60,
        "bonus_base": 350,
        "accent_color": 0xFFDD44,
        "pool": [
            # Common (60%)
            {"id": "MUSTARD",     "name": "Senape",            "rarity": "COM", "xp_mul": 1.0},
            {"id": "WHITE_SAGE",  "name": "Salvia Bianca",     "rarity": "COM", "xp_mul": 1.0},
            {"id": "HOLY_BASIL",  "name": "Basilico Sacro",    "rarity": "COM", "xp_mul": 1.2},
            # Rare (30%)
            {"id": "OLIVE",       "name": "Ulivo",             "rarity": "RAR", "xp_mul": 1.5},
            {"id": "GRAPEVINE",   "name": "Vite",              "rarity": "RAR", "xp_mul": 1.5},
            {"id": "CEDAR",       "name": "Cedro",             "rarity": "RAR", "xp_mul": 1.7},
            {"id": "SANDALWOOD",  "name": "Sandalo",           "rarity": "RAR", "xp_mul": 1.8},
            # Legendary (10%)
            {"id": "FRANKINCENSE","name": "Incenso",           "rarity": "LEG", "xp_mul": 2.5},
            {"id": "PALO_SANTO",  "name": "Palo Santo",        "rarity": "LEG", "xp_mul": 2.8},
            {"id": "LOTUS",       "name": "Loto",              "rarity": "LEG", "xp_mul": 3.5},
            {"id": "TAMARIX",       "name": "Tamarisco",              "rarity": "LEG", "xp_mul": 5}
        ]
    },
    {
        "id": "SEED_COVENANT",
        "name": "Covenant",
        "target_sec": 60 * 60,
        "bonus_base": 1500,
        "accent_color": 0xBD10E0,
        "pool": [
            # Common (60%)
            {"id": "DAISY",         "name": "Margherita",      "rarity": "COM", "xp_mul": 1.0},
            {"id": "VIOLET",        "name": "Viola",           "rarity": "COM", "xp_mul": 1.0},
            {"id": "IVY",           "name": "Edera",           "rarity": "COM", "xp_mul": 1.0},
            {"id": "CORNFLOWER",    "name": "Fiordaliso",      "rarity": "COM", "xp_mul": 1.0},
            # Rare (30%)
            {"id": "TULIP",         "name": "Tulipano",        "rarity": "RAR", "xp_mul": 1.5},
            {"id": "LAVENDER",      "name": "Lavanda",         "rarity": "RAR", "xp_mul": 1.5},
            {"id": "MYRTLE",        "name": "Mirto",           "rarity": "RAR", "xp_mul": 1.5},
            {"id": "JASMINE",       "name": "Gelsomino",       "rarity": "RAR", "xp_mul": 1.8},
            # Legendary (10%)
            {"id": "ROSE",          "name": "Rosa",            "rarity": "LEG", "xp_mul": 2.5},
            {"id": "FORGET_ME_NOT", "name": "Nontiscordardime","rarity": "LEG", "xp_mul": 3.0}
        ]
    }
]
