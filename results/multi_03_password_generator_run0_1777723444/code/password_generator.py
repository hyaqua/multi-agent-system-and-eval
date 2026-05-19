#!/usr/bin/env python3
"""
Password Generator — a REPL-based tool for generating secure passwords and passphrases.

Supports toggling character sets, adjusting length, ambiguous-character exclusion,
strength rating, and passphrase generation using the EFF short wordlist.
"""

import secrets
import string
import math
import sys
from dataclasses import dataclass, field
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Ambiguous characters
# ---------------------------------------------------------------------------

AMBIGUOUS_CHARACTERS = frozenset("0O1lI")


# ---------------------------------------------------------------------------
# Wordlist — EFF short wordlist (1296 Diceware words)
# ---------------------------------------------------------------------------

WORDS: List[str] = [
    "abacus", "abdomen", "abdominal", "abide", "abiding", "ability", "ablaze",
    "able", "abnormal", "abrasion", "abrasive", "abreast", "abridge", "abroad",
    "abruptly", "absence", "absentee", "absently", "absinthe", "absolute",
    "absolve", "abstain", "abstract", "absurd", "accent", "acclaim", "acclimate",
    "accolade", "accompany", "accord", "accost", "account", "accrue", "accuse",
    "acedia", "acetate", "acetic", "acetone", "achieve", "acidify", "acidity",
    "acknowledge", "acorn", "acquaint", "acquire", "acquit", "acrobat", "acronym",
    "acting", "action", "activate", "activist", "actor", "actual", "acumen",
    "adapter", "addendum", "addict", "addition", "adhesive", "adjacent", "adjoin",
    "adjourn", "adjudge", "adjust", "admiral", "admire", "admit", "admonish",
    "adopt", "adorn", "adrift", "adroit", "adult", "advance", "adverb",
    "adverse", "advert", "advise", "aegis", "aerate", "aerial", "aerosol",
    "affable", "affair", "affect", "affidavit", "affiliate", "affirm", "affix",
    "afflict", "afford", "affront", "afloat", "afraid", "afterglow", "afterlife",
    "aftermath", "agape", "agar", "agate", "agenda", "agent", "aggregate",
    "agile", "aging", "agitate", "agnostic", "agony", "aground", "ahead",
    "airfield", "airfoil", "airlift", "airline", "airlock", "airman", "airmass",
    "airmen", "airplane", "airway", "ajar", "akimbo", "alarm", "albedo",
    "alchemy", "alcohol", "alcove", "alder", "aleck", "alert", "alfalfa",
    "algae", "algebra", "alias", "alibi", "alien", "alight", "align", "alike",
    "alkali", "alkyd", "allege", "alley", "allied", "allot", "allow", "alloy",
    "allude", "almond", "almost", "aloft", "aloha", "alone", "alongside",
    "aloof", "alpaca", "alphabet", "alpine", "already", "also", "altar",
    "alter", "although", "altitude", "alumni", "always", "amaretto",
    "amaze", "amazon", "amber", "ambient", "amble", "ambrosia", "ambulance",
    "amend", "amiable", "amicable", "amidst", "ammonia", "amnesia", "amnesty",
    "amongst", "amount", "amphora", "ample", "amplify", "amputee", "amulet",
    "amuse", "anagram", "analogy", "analysis", "analyst", "anarchy", "anatomy",
    "anchor", "android", "anemia", "anemone", "anew", "angelic", "anger",
    "angler", "angles", "angular", "animal", "anise", "ankle", "annex",
    "annotate", "annoy", "annual", "anode", "anomaly", "answer", "anteater",
    "antenna", "anthem", "anthill", "anthrax", "antic", "antidote", "antique",
    "antler", "anvil", "anxiety", "anybody", "anyhow", "anymore", "anyplace",
    "anytime", "aorta", "apart", "apathy", "apiece", "apnea", "apogee",
    "apology", "appeal", "appear", "appease", "appendix", "appetite", "applaud",
    "apple", "apply", "appoint", "appraise", "approach", "approve", "apricot",
    "apron", "aptitude", "aquaria", "aquatic", "arbiter", "arbitrary", "arbor",
    "arcade", "archer", "archive", "arctic", "ardent", "arena", "argon",
    "argue", "arise", "arkansas", "armada", "armchair", "armful", "armhole",
    "armlet", "armory", "armpit", "armrest", "aroma", "arose", "around",
    "arousal", "arrange", "array", "arrest", "arrival", "arrive", "arrow",
    "arson", "artery", "artful", "article", "artisan", "ascent", "ascribe",
    "ashore", "ashtray", "aside", "askance", "asleep", "aspect", "asphalt",
    "aspirin", "assault", "assemble", "assert", "assess", "asset", "assign",
    "assist", "assume", "assure", "asthma", "astride", "astute", "asylum",
    "atlas", "atoll", "atomic", "atone", "atrium", "attach", "attack",
    "attain", "attend", "attest", "attic", "attire", "auction", "audible",
    "audio", "audit", "auger", "augment", "aunt", "austere", "author",
    "autism", "autumn", "avail", "avatar", "avenue", "average", "aversion",
    "aviation", "avid", "avocado", "avoid", "awaken", "award", "awesome",
    "awful", "awhile", "awkward", "awning", "awoke", "axion", "axis",
    "axle", "axolotl", "azalea",
    "baboon", "backbone", "backer", "backfire", "backlog", "backpack",
    "backside", "backspin", "backup", "bacon", "badge", "baffle", "bagel",
    "baggage", "baggy", "bagpipe", "bailiff", "bakery", "balance", "balcony",
    "ballast", "ballet", "balloon", "ballot", "bambino", "bamboo", "banana",
    "bandana", "bandit", "banish", "banjo", "banker", "banner", "banquet",
    "barbecue", "barber", "barely", "bargain", "barge", "baritone", "barnacle",
    "baron", "barrack", "barrel", "barrier", "barter", "baseball", "basement",
    "bashful", "basin", "basket", "bassoon", "batch", "bathmat", "bathroom",
    "bathtub", "batik", "baton", "battalion", "battery", "battle", "bayou",
    "bazaar", "beacon", "beagle", "beaker", "beaming", "beanbag", "bearcat",
    "beard", "bearer", "beast", "beatnik", "beauty", "become", "bedbug",
    "bedrock", "bedroom", "bedsheet", "bedside", "bedspread", "beefsteak",
    "beehive", "beeline", "beeswax", "beetle", "befall", "befit", "before",
    "beggar", "begin", "behalf", "behave", "behind", "behold", "beige",
    "belief", "believe", "bellows", "belong", "beltway", "bench", "bend",
    "beneath", "benefit", "berth", "beset", "besides", "bestow", "betray",
    "better", "between", "beverage", "beware", "beyond", "bias", "bible",
    "bicep", "bicker", "bicycle", "bidder", "bifocal", "biggest", "bighorn",
    "bikini", "bilge", "billfold", "billow", "bimini", "binary", "binder",
    "binge", "bingo", "biopsy", "birch", "birth", "biscuit", "bishop",
    "bismuth", "bison", "bisque", "bistro", "bitten", "bitter", "bizarre",
    "blacken", "blackout", "bladder", "blame", "blandish", "blanket", "blarney",
    "blaster", "blatant", "blazer", "bleach", "bleak", "blemish", "blender",
    "bless", "blight", "blimp", "blind", "blinker", "blissful", "blister",
    "blitz", "blizzard", "bloat", "blockade", "blogger", "blond", "blood",
    "bloom", "blossom", "blouse", "blubber", "bludgeon", "bluejay", "blunder",
    "blunt", "blurb", "blurt", "blush", "boast", "boatman", "bobbin",
    "bobcat", "bodily", "bodywork", "bogey", "bogus", "boiler", "bold",
    "bolster", "bomber", "bondage", "bonehead", "bonfire", "bongo", "bonnet",
    "bonus", "boogey", "bookcase", "bookish", "booklet", "boom", "booster",
    "bootleg", "border", "borealis", "boring", "borrow", "bossy", "botany",
    "bother", "bottle", "bottom", "boulder", "bounce", "bound", "bounty",
    "boutique", "bovid", "bowel", "bowhead", "bowler", "bowline", "boxcar",
    "boxer", "boycott", "braces", "bracket", "brad", "bragger", "braid",
    "brain", "brake", "branch", "brandish", "brandy", "brass", "bravado",
    "bravo", "brawler", "brazen", "bread", "break", "breathe", "breeder",
    "brevity", "brewery", "bribe", "brick", "bridal", "bridge", "brief",
    "brigade", "bright", "brim", "bring", "brink", "brisk", "bristle",
    "brittle", "broad", "broccoli", "brochure", "broiler", "broken", "bronco",
    "bronze", "brooch", "brood", "brook", "broom", "broth", "browbeat",
    "brownie", "browser", "bruise", "brunch", "brunette", "brush", "brusque",
    "brutal", "bubble", "bucket", "buckle", "budget", "buffalo", "buffer",
    "buffet", "buggy", "bugle", "builder", "bulb", "bulge", "bulk",
    "bulldog", "bulldoze", "bullet", "bullfrog", "bullseye", "bully", "bumble",
    "bumper", "bundle", "bungalow", "bungee", "bunker", "bunny", "buoy",
    "burden", "bureau", "burger", "burglar", "burial", "burly", "burner",
    "burrito", "burrow", "burst", "busboy", "bush", "bushel", "business",
    "bustle", "butane", "butler", "butter", "button", "buyout", "buzzard",
    "buzzer", "bygone", "byline", "bypass", "bypath", "byway",
    "cabana", "cabbie", "cabinet", "cable", "caboose", "cacao", "cache",
    "cackle", "cactus", "cadet", "cafe", "caffeine", "cagey", "cairn",
    "calcium", "calculus", "caliber", "calico", "caller", "calm", "calorie",
    "calumny", "calypso", "camaro", "camber", "camel", "camera", "camisole",
    "campaign", "campfire", "campus", "canal", "canary", "cancel", "cancer",
    "candid", "candle", "candy", "canine", "canister", "cannery", "cannon",
    "cannot", "canoe", "canon", "canopy", "canteen", "canvas", "canyon",
    "capable", "capital", "capo", "capsule", "captain", "caption", "captive",
    "capture", "carafe", "caramel", "carat", "carbon", "carboy", "carcass",
    "cardiac", "career", "careful", "caress", "cargo", "caribou", "carillon",
    "carnival", "carob", "carol", "carpet", "carport", "carriage", "carrier",
    "carrot", "carry", "cartel", "carton", "carver", "casein", "cashew",
    "casino", "casket", "cassava", "cassette", "cassock", "castle", "casual",
    "catalog", "catalyst", "catcher", "cater", "catfish", "cathedral", "catnip",
    "cattle", "caucus", "cauldron", "caution", "cavalier", "cavalry", "cavern",
    "caviar", "cayenne", "cease", "cedar", "celery", "celestial", "cellar",
    "cellist", "cello", "cement", "censor", "census", "centaur", "century",
    "ceramic", "cereal", "certify", "cesspool", "chafe", "chaise", "chalet",
    "chalice", "chamber", "champ", "chance", "change", "channel", "chant",
    "chapel", "chapter", "charade", "charge", "chariot", "charity", "charm",
    "chart", "chase", "chasm", "chassis", "chatter", "cheap", "check",
    "cheddar", "cheek", "cheer", "cheese", "cheetah", "chef", "chelate",
    "chemical", "cherish", "cherry", "chess", "chestnut", "chevron", "chew",
    "chic", "chicken", "chief", "child", "chill", "chime", "chimney",
    "china", "chintz", "chipmunk", "chive", "chloral", "chocolate", "choice",
    "choir", "choke", "chomp", "choose", "chopper", "chord", "chowder",
    "chrome", "chubby", "chuckle", "chunk", "church", "churn", "chute",
    "cider", "cigar", "cinch", "cinema", "cinnamon", "cipher", "circle",
    "circus", "citadel", "citizen", "citron", "citrus", "city", "civet",
    "civil", "clad", "claim", "clam", "clammy", "clamp", "clang",
    "clarity", "clash", "clasp", "classic", "clatter", "clause", "clavicle",
    "claw", "clay", "cleaner", "cleanse", "clear", "cleat", "cleaver",
    "cleft", "clergy", "cleric", "clerk", "clever", "cliche", "click",
    "client", "cliff", "climate", "clincher", "cling", "clinic", "clip",
    "cloak", "clock", "clod", "clog", "clone", "closeup", "closure",
    "cloth", "cloture", "cloud", "clout", "clover", "club", "cluck",
    "clue", "clump", "clumsy", "cluster", "clutch", "coach", "coal",
    "coarse", "coast", "coax", "cobalt", "cobble", "cobra", "cockpit",
    "cocktail", "cocoa", "coconut", "coddle", "codex", "coerce", "coffee",
    "coffer", "coffin", "cogent", "cognac", "cohere", "cohort", "coil",
    "coinage", "coincide", "colander", "cold", "coleslaw", "colic", "colitis",
    "collage", "collar", "collect", "college", "collide", "colloid", "colon",
    "colony", "color", "colt", "column", "combat", "combine", "combust",
    "comedy", "comet", "comfort", "comic", "comma", "command", "commend",
    "comment", "commit", "commode", "common", "commune", "compact", "company",
    "compare", "compel", "compete", "compile", "complex", "comply", "comport",
    "compose", "compost", "compote", "compress", "comprise", "compute",
    "comrade", "conceal", "concede", "concept", "concern", "concert",
    "conch", "concise", "concoct", "concord", "concur", "condo", "condone",
    "conduct", "confer", "confess", "confide", "confine", "confirm",
    "conflict", "conform", "confound", "congeal", "congest", "conifer",
    "conjoin", "conjure", "connect", "conquer", "consign", "consist",
    "console", "consort", "conspire", "constant", "constrict", "consul",
    "consult", "consume", "contact", "contain", "contend", "content",
    "contest", "context", "contort", "contour", "control", "convect",
    "convene", "convent", "convert", "convex", "convey", "convict",
    "convoy", "convulse", "cooker", "cookie", "cooler", "copilot", "copper",
    "copula", "copycat", "coral", "cord", "cordial", "cordite", "corduroy",
    "core", "cork", "cornea", "corner", "corpse", "corpus", "correct",
    "corridor", "corrode", "corsair", "corset", "cortex", "cosign", "cosmic",
    "cosmos", "costume", "cosy", "cotton", "couch", "cougar", "cough",
    "council", "counsel", "counter", "county", "couple", "coupon", "course",
    "court", "cousin", "coven", "covert", "coward", "cowbell", "cowboy",
    "coyote", "crab", "crack", "cradle", "craft", "crag", "cram",
    "cranberry", "crane", "crater", "crawfish", "crawl", "crayon", "crazy",
    "creak", "cream", "creation", "credit", "creed", "creek", "creep",
    "creole", "crepe", "crescent", "crest", "crevice", "crewcut", "crewman",
    "crib", "cricket", "crier", "crime", "crimson", "cringe", "cripple",
    "crisis", "crisp", "critic", "croak", "crock", "croissant", "crone",
    "crook", "croon", "crosier", "cross", "crouton", "crowbar", "crown",
    "crucial", "crude", "cruel", "cruise", "crumb", "crumple", "crunch",
    "crust", "cryptic", "crystal", "cubicle", "cuckoo", "cucumber", "cudgel",
    "cufflink", "culprit", "cult", "cumin", "cupcake", "cupful", "cupola",
    "curator", "curdle", "cure", "curfew", "curio", "curl", "currant",
    "current", "curry", "cursive", "cursor", "curtail", "curtain", "curtsey",
    "curve", "cushion", "custody", "custom", "cutback", "cute", "cuticle",
    "cutlass", "cutlet", "cutoff", "cutter", "cyanide", "cyborg", "cyclone",
    "cyclops", "cygnet", "cylinder", "cymbal", "cynic", "cypress", "czar",
    "dabble", "dad", "daffodil", "dagger", "daily", "dainty", "dairy",
    "dais", "daisy", "damage", "dame", "damn", "damp", "dancer",
    "dandelion", "dandruff", "danger", "dangle", "daredevil", "darkroom",
    "darling", "dart", "dash", "data", "date", "daub", "daunt",
    "dawdle", "dawn", "daybed", "daydream", "daylight", "daze", "dazzle",
    "deacon", "deadline", "deaf", "deal", "dear", "deathbed", "debacle",
    "debate", "debit", "debris", "debt", "debug", "decade", "decaf",
    "decal", "decay", "deceit", "decide", "deckle", "declare", "decline",
    "decor", "decrease", "decree", "deduce", "deed", "deepen", "deface",
    "defame", "defeat", "defect", "defend", "defer", "defiant", "deficit",
    "define", "deflate", "deflect", "defog", "defraud", "defrost", "deft",
    "defuse", "degree", "dehydrate", "deify", "deign", "deity", "delay",
    "delete", "delicacy", "delight", "delirium", "deliver", "delta", "delude",
    "deluge", "deluxe", "delve", "demand", "demented", "demise", "demo",
    "demote", "demure", "denial", "denote", "dense", "dental", "dentist",
    "depart", "depend", "depict", "deplete", "deploy", "deport", "deposit",
    "deprave", "deprive", "derange", "deride", "derive", "descend", "desert",
    "design", "desire", "desist", "desktop", "desolate", "despair", "despise",
    "destine", "destiny", "destroy", "detach", "detail", "detect", "detente",
    "detest", "detonate", "detour", "detox", "deuce", "devastate", "develop",
    "device", "devious", "devise", "devoid", "devote", "devour", "dew",
    "dexter", "diabetic", "diabolic", "diadem", "dialect", "diamond", "diaper",
    "diary", "dice", "dictator", "diction", "diesel", "dietary", "differ",
    "diffuse", "digest", "digit", "dignify", "dignity", "dilemma", "dilute",
    "dime", "dimple", "diner", "dinghy", "dining", "dinner", "diocesan",
    "dioxide", "diploma", "direct", "dirt", "disable", "disarm", "discard",
    "discern", "disco", "discord", "discuss", "disdain", "disease", "disgrace",
    "disguise", "disgust", "dish", "dislodge", "dismay", "dismiss", "disorder",
    "dispatch", "dispel", "display", "dispute", "disrupt", "dissent", "dissolve",
    "distance", "distinct", "distort", "distract", "distress", "district",
    "disturb", "ditch", "ditto", "dive", "divert", "divide", "divine",
    "divorce", "dizzy", "dock", "doctrine", "document", "dodge", "dogged",
    "dogma", "doldrums", "dollop", "dolphin", "domain", "domino", "donate",
    "donkey", "donor", "doorman", "doorstep", "dormant", "dosage", "doublet",
    "doubt", "doughnut", "dovetail", "dowdy", "dowel", "downcast", "downfall",
    "downpour", "downtown", "downward", "doze", "drab", "draft", "dragon",
    "drain", "drama", "drape", "draw", "dread", "dream", "dredge",
    "drench", "dress", "dribble", "drift", "drill", "drinker", "drip",
    "drive", "drizzle", "drone", "drool", "droop", "dropout", "drought",
    "drove", "drown", "drowsy", "drudge", "drummer", "drunk", "dryer",
    "dual", "dubious", "duchess", "duckling", "duct", "duel", "duet",
    "duffel", "dugout", "dulcet", "dull", "dumb", "dumbbell", "dummy",
    "dump", "dunce", "dune", "dung", "dungeon", "dunno", "duo",
    "duplex", "durable", "dusk", "dust", "duty", "dwarf", "dwell",
    "dwindle", "dye", "dynamic", "dynamo", "dynasty", "dyslexia",
    "eager", "eagle", "earache", "earlobe", "earmark", "earmuff", "earner",
    "earplug", "earth", "earwig", "easel", "eastern", "eavesdrop", "ebony",
    "echo", "eclair", "eclectic", "eclipse", "ecology", "economy", "ecstasy",
    "ectopic", "eddy", "edema", "edger", "edible", "edict", "edifice",
    "editor", "educate", "eel", "eerie", "efface", "effect", "effigy",
    "effort", "egghead", "eggnog", "eggplant", "egoist", "eider", "eight",
    "either", "eject", "elapse", "elastic", "elbow", "elder", "elect",
    "elegant", "element", "elephant", "elevate", "elfin", "elicit", "elide",
    "elite", "elixir", "ellipse", "elm", "elope", "elude", "email",
    "embalm", "embark", "embassy", "emblem", "embody", "embrace", "embroider",
    "embryo", "emerald", "emerge", "emeritus", "emery", "emetic", "emigre",
    "eminent", "emirate", "emissary", "emit", "emotion", "emperor", "empire",
    "employ", "empower", "empress", "empty", "enable", "enact", "enamel",
    "encase", "enclave", "enclose", "encode", "encore", "encrust", "encrypt",
    "endanger", "endear", "endive", "endure", "enemy", "energy", "enforce",
    "engage", "engine", "engrave", "enhance", "enigma", "enjoy", "enlarge",
    "enlighten", "enlist", "enquire", "enrage", "enrich", "enroll", "enshrine",
    "ensign", "enslave", "ensnare", "ensure", "entail", "enter", "entice",
    "entire", "entrant", "entreat", "entropy", "envelop", "envious", "envision",
    "enzyme", "epic", "epidemic", "epigram", "episode", "equal", "equator",
    "equine", "equip", "equity", "erasure", "erect", "erode", "errant",
    "erratic", "error", "erupt", "escalate", "escape", "eschew", "escort",
    "espresso", "essay", "estate", "esteem", "estrogen", "etching", "eternal",
    "ethic", "ethnic", "ethyl", "euchre", "eulogy", "euphoria", "evacuate",
    "evade", "evaluate", "evaporate", "eve", "even", "event", "evergreen",
    "everyday", "evict", "evident", "evil", "evoke", "evolve", "exact",
    "exalt", "examine", "example", "excavate", "exceed", "excerpt", "excess",
    "exchange", "excite", "exclude", "excuse", "execute", "exempt", "exert",
    "exhale", "exhaust", "exhibit", "exile", "exist", "exodus", "exotic",
    "expand", "expect", "expel", "expend", "expert", "expire", "explain",
    "explicit", "explode", "exploit", "explore", "export", "expose", "express",
    "expunge", "extend", "extinct", "extort", "extract", "extreme", "exude",
    "eyebrow", "eyedrop", "eyelash", "eyelid", "eyesight",
    "fable", "fabric", "facade", "facet", "facility", "faction", "factor",
    "fade", "falcon", "fallacy", "fallout", "famine", "famish", "fanatic",
    "fancier", "fancy", "fang", "fantasy", "farewell", "farmhand", "farmer",
    "farthing", "fast", "fate", "father", "fatigue", "faucet", "fault",
    "favor", "fawn", "faze", "fearful", "feast", "feather", "feature",
    "federal", "feeble", "feedback", "feisty", "feline", "fellow", "felony",
    "felt", "female", "feminine", "fence", "fender", "ferment", "ferret",
    "ferry", "fertile", "festive", "fetch", "fetter", "feud", "fever",
    "fiancee", "fiasco", "fickle", "fiction", "fiddle", "fidget", "field",
    "fiend", "fierce", "fiesta", "fifteen", "fifty", "figment", "figure",
    "filament", "filbert", "filch", "file", "finale", "finance", "finder",
    "finesse", "finger", "finicky", "finish", "finite", "fir", "fireball",
    "firebug", "firefly", "fireman", "firework", "fiscal", "fishbowl",
    "fisher", "fishnet", "fissure", "fist", "fixate", "fizzle", "flagon",
    "flair", "flame", "flange", "flannel", "flash", "flask", "flatbed",
    "flaunt", "flavor", "flax", "fleck", "fledge", "fleece", "fleet",
    "flesh", "flex", "flicker", "flier", "flight", "flimsy", "fling",
    "flint", "flip", "flipper", "flirt", "float", "flock", "flood",
    "floor", "floppy", "flora", "florid", "florist", "flotsam", "flounce",
    "flourish", "flower", "fluent", "fluff", "fluid", "fluke", "flunk",
    "flurry", "flush", "fluster", "flutter", "flux", "flyer", "foal",
    "foam", "focal", "focus", "fogey", "foggy", "foible", "foist",
    "fold", "foliage", "folklore", "follow", "folly", "fondue", "font",
    "foolish", "footage", "football", "footman", "footnote", "footpath",
    "footrest", "footstep", "footwear", "forage", "foray", "forbear",
    "forbid", "force", "ford", "forearm", "forecast", "forego", "foreign",
    "forensic", "foresee", "forest", "forever", "forfeit", "forge", "forgive",
    "fork", "form", "formal", "format", "former", "formula", "forsake",
    "fortify", "fortress", "fortune", "forward", "fossil", "foster", "foul",
    "founder", "fountain", "four", "fowl", "foyer", "fractal", "fraction",
    "fracture", "fragile", "fragrant", "frail", "frame", "frank", "frantic",
    "fraud", "fray", "freak", "freckle", "freedom", "freeway", "freeze",
    "freight", "frenzy", "frequent", "fresh", "fret", "friar", "friday",
    "fridge", "friend", "fright", "fringe", "frisbee", "frisk", "fritter",
    "frivol", "frock", "frogman", "front", "frost", "froth", "frown",
    "frozen", "frugal", "fruit", "frustrate", "fry", "fudge", "fuel",
    "fugitive", "fulcrum", "fumble", "fume", "fun", "function", "fungus",
    "funnel", "furry", "fuse", "fuss", "futile", "future", "fuzzy",
    "gable", "gadget", "gaffe", "gag", "gaiety", "gait", "galactic",
    "galaxy", "gallant", "gallery", "gallop", "gambit", "gambler", "game",
    "gander", "gangway", "garage", "garbage", "garden", "gargle", "garland",
    "garlic", "garment", "garnish", "garter", "gaslight", "gasoline", "gasket",
    "gasp", "gastric", "gateway", "gather", "gauntlet", "gauze", "gavel",
    "gawky", "gazelle", "gazer", "gazette", "gecko", "geese", "gelatin",
    "gem", "gender", "general", "generic", "genesis", "genetic", "genie",
    "genius", "genre", "gentle", "genuine", "genus", "geode", "geology",
    "geometry", "gerbil", "gesture", "getaway", "geyser", "ghetto", "ghost",
    "giant", "giddy", "gift", "gigantic", "giggle", "gimmick", "ginger",
    "giraffe", "girdle", "girl", "gist", "giveaway", "glacier", "glad",
    "glamour", "gland", "glare", "glaze", "gleam", "glide", "glimmer",
    "glimpse", "glisten", "glitch", "glitter", "gloat", "global", "gloom",
    "glossy", "glove", "glowworm", "glucose", "glue", "glutton", "glycerin",
    "glyph", "gnarl", "gnat", "gnaw", "gnome", "goad", "gobble",
    "goblet", "godchild", "godfather", "godlike", "godson", "goggle", "golden",
    "goldfish", "golf", "golly", "gondola", "gong", "goodbye", "goofy",
    "goose", "gopher", "gorilla", "gospel", "gossip", "gothic", "gouge",
    "gourd", "gourmet", "gout", "govern", "gown", "grab", "grace",
    "gradient", "graft", "grain", "grammar", "granary", "grand", "granite",
    "grant", "grape", "graphic", "grapple", "grasp", "grass", "grate",
    "grateful", "gratify", "grating", "gratis", "gratuity", "grave", "gravel",
    "gravity", "gravy", "gray", "graze", "grease", "greedy", "green",
    "greet", "grenade", "grey", "griddle", "grief", "griffin", "grill",
    "grim", "grime", "grin", "gripe", "gristle", "grit", "grizzly",
    "groan", "grocer", "groom", "groove", "gross", "grouch", "ground",
    "group", "grove", "grow", "grub", "grudge", "gruel", "gruesome",
    "gruff", "grumble", "grunt", "guard", "guess", "guest", "guide",
    "guild", "guile", "guilt", "guinea", "guitar", "gulch", "gulf",
    "gull", "gully", "gulp", "gumball", "gumdrop", "gunboat", "gunfire",
    "gunner", "gunshot", "gurgle", "guru", "gush", "gusset", "gust",
    "gut", "gutter", "guy", "guzzle", "gymkhana", "gymnast", "gypsum",
    "gyrate", "habitat", "habitual", "hacienda", "hacksaw", "haggard", "haggle",
    "haircut", "halfback", "halftime", "hallmark", "hallway", "halogen",
    "halt", "halter", "hamlet", "hammer", "hammock", "hamper", "hamster",
    "hamstring", "handbag", "handball", "handbill", "handbook", "handcuff",
    "handful", "handgun", "handicap", "handle", "handmade", "handout",
    "handrail", "handset", "handsome", "handyman", "hangar", "hanger",
    "hangout", "hangup", "hankie", "happen", "harass", "harbor", "hardcopy",
    "harden", "hardhat", "hardly", "hardtop", "hardware", "hare", "harm",
    "harness", "harp", "harpoon", "harrow", "harsh", "harvest", "hash",
    "hassle", "haste", "hatbox", "hatchet", "hate", "haughty", "haul",
    "haunt", "haven", "havoc", "hawk", "hawser", "haystack", "hazard",
    "hazel", "headache", "headland", "headline", "headlock", "headlong",
    "headrest", "headroom", "headset", "headway", "heal", "health", "heap",
    "hearing", "hearse", "heart", "heathen", "heather", "heaven", "heckle",
    "hectic", "hedge", "heedless", "hefty", "heifer", "height", "heirloom",
    "heist", "helical", "helium", "helmet", "helmsman", "helpful", "hem",
    "henchman", "henna", "hepatic", "herald", "herbal", "herbicide", "herd",
    "hereby", "hereof", "heresy", "heritage", "hermit", "heroic", "heron",
    "herpes", "hesitant", "hexagon", "heyday", "hiatus", "hiccup", "hickory",
    "hideaway", "hideout", "hierarch", "highland", "highway", "hijack",
    "hiker", "hilarity", "hilltop", "hilt", "hinder", "hinge", "hint",
    "hipbone", "hippo", "hire", "hiss", "history", "hitcher", "hitchhike",
    "hither", "hive", "hoagie", "hoard", "hoax", "hobble", "hobby",
    "hockey", "hogan", "hoist", "holdout", "hole", "holiday", "holler",
    "hollow", "homebody", "homeland", "homepage", "hometown", "homework",
    "homicide", "homily", "honest", "honeybee", "honeydew", "honor", "hood",
    "hoof", "hookah", "hookup", "hoop", "hooray", "hoot", "hoover",
    "hopeful", "hopper", "horizon", "hormone", "hornet", "horoscope",
    "horrible", "horror", "horse", "hose", "hospice", "hostage", "hostel",
    "hostess", "hostile", "hotcake", "hotel", "hound", "house", "hover",
    "howdy", "hubcap", "huddle", "huff", "hugger", "hull", "human",
    "humble", "humidor", "humor", "hunch", "hundred", "hunter", "hurdle",
    "hurl", "hurrah", "hurricane", "husband", "hush", "husky", "hustle",
    "hutch", "hyacinth", "hybrid", "hydrant", "hydrate", "hydrogen", "hyena",
    "hygiene", "hymn", "hype", "hyphen", "hypnosis", "hyssop",
    "iceberg", "icebox", "icicle", "icon", "idea", "idle", "idol",
    "igloo", "ignore", "iguana", "illegal", "illume", "illusion", "image",
    "imagine", "imbed", "imitate", "immense", "immerse", "immune", "impact",
    "impair", "impasse", "impeach", "impede", "impel", "imperial", "imperil",
    "impetus", "impinge", "implant", "imply", "import", "impose", "imprint",
    "improve", "impulse", "inane", "inboard", "inborn", "inbound", "incense",
    "inch", "incite", "include", "income", "increase", "indeed", "index",
    "indicate", "indigo", "indoor", "induce", "inept", "inert", "infamy",
    "infant", "infect", "inflame", "inflow", "influx", "inform", "infringe",
    "infuse", "ingest", "inhabit", "inhale", "inherit", "inject", "injure",
    "inkblot", "inkling", "inlet", "inmate", "innocent", "input", "inquest",
    "inquiry", "insane", "insect", "insert", "inshore", "inside", "insist",
    "insomnia", "inspect", "inspire", "install", "instant", "instead",
    "instep", "insulin", "insult", "intact", "intake", "integer", "intend",
    "intercom", "interest", "interim", "interior", "internal", "internet",
    "interval", "intimate", "intone", "intrepid", "intrigue", "invade",
    "invalid", "inveigh", "invent", "inverse", "invest", "invite", "invoice",
    "invoke", "involve", "iodine", "ion", "ire", "iridium", "iris",
    "irony", "island", "isolate", "isotope", "issue", "italic", "item",
    "itinerary", "ivory", "ivy",
    "jab", "jackal", "jacket", "jackpot", "jagged", "jaguar", "jail",
    "jamboree", "janitor", "jargon", "jarring", "jasmine", "jaundice", "jaunt",
    "javelin", "jawbone", "jaywalk", "jazz", "jealous", "jeans", "jeep",
    "jelly", "jeopardy", "jerk", "jersey", "jest", "jetsam", "jewel",
    "jigsaw", "jingle", "jinx", "jitter", "jive", "job", "jockey",
    "jogger", "join", "joint", "joker", "jollity", "jostle", "journal",
    "journey", "jovial", "juggle", "jumbo", "jump", "jungle", "junior",
    "juniper", "junk", "jurist", "juror", "justify", "juvenile",
    "kangaroo", "kaolin", "kapok", "karate", "karma", "kayak", "kebab",
    "keen", "keeper", "kennel", "kept", "kerchief", "kernel", "kerosene",
    "ketchup", "kettle", "keyhole", "keyword", "khaki", "kibbutz", "kick",
    "kidnap", "kidney", "killer", "kiln", "kilo", "kilt", "kimono",
    "kinase", "kindred", "kinetic", "kingpin", "kiosk", "kipper", "kismet",
    "kiss", "kitchen", "kite", "kitten", "knack", "knead", "knee",
    "knight", "knit", "knock", "knot", "knowhow", "knuckle", "koala",
    "kook", "kosher", "krypton", "kudos", "kungfu",
    "lab", "label", "lacerate", "lackey", "lacquer", "ladder", "lagoon",
    "lambda", "lament", "lampoon", "lance", "landline", "landlord", "landmark",
    "landslide", "language", "lanky", "lanolin", "lantern", "lanyard", "lapdog",
    "lapel", "lapse", "laptop", "larceny", "lard", "largesse", "lariat",
    "larva", "larynx", "laser", "lasso", "latent", "latex", "latitude",
    "latter", "lattic", "laugh", "launch", "laundry", "laurel", "lavender",
    "layman", "layout", "lazy", "lead", "leaflet", "league", "leak",
    "learn", "lease", "leather", "lectern", "lecture", "ledge", "leeway",
    "legacy", "legion", "legume", "leisure", "lemma", "lemonade", "lemur",
    "lens", "leopard", "leprosy", "lesion", "lesson", "letter", "lettuce",
    "lever", "lexicon", "liable", "liar", "liberal", "liberty", "library",
    "license", "lichen", "lift", "ligament", "lighthouse", "likewise", "lilac",
    "limb", "lime", "limit", "limousine", "lineage", "linen", "linger",
    "linguini", "linkage", "lint", "lion", "lip", "liqueur", "liquid",
    "lisp", "listen", "litany", "lithium", "litmus", "litter", "liver",
    "lizard", "llama", "loaf", "loan", "loathe", "lobby", "lobe",
    "lobster", "locale", "locate", "locker", "locust", "lodge", "loft",
    "logger", "logic", "loin", "lonely", "loom", "loop", "loot",
    "lordship", "lotion", "lottery", "loud", "lounge", "louse", "louver",
    "love", "lower", "lucid", "luck", "luggage", "lullaby", "lumbar",
    "lumen", "lunar", "lunch", "lunette", "lung", "lurch", "lure",
    "lurk", "luster", "lute", "luxury", "lymph", "lynx", "lyric",
    "macabre", "macaroni", "machine", "macrame", "madam", "mafia", "magazine",
    "maggot", "magic", "magnate", "magnet", "magnify", "magnitude", "mahogany",
    "maiden", "mailbox", "mainland", "mainstay", "majesty", "makeup",
    "malaria", "mall", "mammal", "manacle", "manager", "mandate", "mandolin",
    "manhole", "mania", "manicure", "mankind", "mansion", "mantel", "mantle",
    "manual", "many", "maple", "marathon", "maraud", "marble", "march",
    "mare", "margin", "marigold", "marina", "marinade", "marital", "marker",
    "market", "marmalade", "maroon", "marrow", "marsh", "marshal", "martini",
    "martyr", "marzipan", "masculine", "mask", "mason", "massage", "mast",
    "master", "mastiff", "matador", "match", "mate", "matrix", "matter",
    "mature", "maul", "mauve", "maverick", "maxim", "mayhem", "mayor",
    "meadow", "meager", "meal", "meaning", "measles", "measure", "mechanic",
    "medal", "media", "medic", "medium", "megabyte", "melody", "melon",
    "member", "memory", "menace", "mental", "menthol", "mentor", "mercy",
    "merge", "merit", "mermaid", "mesa", "mesquite", "message", "meteor",
    "meter", "method", "mettle", "micro", "midget", "midriff", "midst",
    "migrant", "mildew", "militant", "militia", "milkman", "millennium",
    "million", "mimicry", "minaret", "miner", "mingle", "mini", "minimum",
    "minnow", "minor", "mintage", "minuscule", "minute", "miracle", "mirage",
    "mirth", "miscue", "misery", "misfire", "mishap", "mislead", "misplace",
    "misprint", "missile", "mission", "missive", "mistake", "mister",
    "mitten", "mixer", "mixture", "moat", "mobile", "mockery", "modem",
    "modern", "modest", "modify", "module", "mogul", "moisten", "molar",
    "mold", "molecule", "mom", "monarch", "monetary", "monitor", "monk",
    "monogram", "monopoly", "monsoon", "monster", "monthly", "monument",
    "moody", "moonbeam", "moor", "moose", "morbid", "morgue", "morning",
    "morose", "morsel", "mortar", "mosaic", "moss", "most", "motel",
    "mother", "motion", "motivate", "motor", "motto", "mousse", "mouth",
    "move", "muck", "mucus", "muddle", "muffin", "muffle", "muggy",
    "mulberry", "mulch", "mule", "mull", "multiple", "mummy", "munch",
    "mural", "murky", "murmur", "muscle", "museum", "mush", "musical",
    "musk", "musket", "mustard", "muster", "mutable", "mutant", "mute",
    "mutiny", "muzzle", "myopia", "myriad", "mystic", "myth",
    "nacelle", "nadir", "naiad", "naive", "naked", "namely", "namesake",
    "nanosecond", "napkin", "narcotic", "narrate", "narrow", "nasal",
    "nasturtium", "nasty", "nation", "native", "nattier", "natural",
    "naughty", "nausea", "nautical", "naval", "nectar", "negate", "neglect",
    "negligee", "neigh", "neon", "nephew", "nerve", "nestle", "neuron",
    "neutral", "neutron", "never", "newborn", "newly", "newscast", "newsreel",
    "nibble", "nicety", "niche", "nickname", "niece", "nightie", "nimble",
    "nimbus", "nimby", "nitrate", "nitrogen", "nobility", "noble", "nobody",
    "nocturnal", "node", "noise", "nomad", "nonce", "noodle", "nook",
    "normal", "nosebleed", "nosegay", "nostril", "notary", "notch", "novel",
    "novice", "nozzle", "nuance", "nuclei", "nudge", "null", "number",
    "numeral", "nun", "nursery", "nurture", "nutcracker", "nylon", "nymph",
    "oaken", "oath", "obese", "obey", "obituary", "object", "oblate",
    "oblige", "obscure", "observe", "obtain", "obtrude", "obvious", "ocarina",
    "occult", "ocean", "octopus", "ocular", "oddity", "ode", "offal",
    "offend", "offer", "offhand", "office", "officer", "offload", "offset",
    "often", "oilcloth", "oilskin", "ointment", "okra", "olive", "omega",
    "omelet", "omen", "omit", "omnibus", "onboard", "oneness", "onerous",
    "oneself", "onetime", "ongoing", "online", "onrush", "onset", "onstage",
    "onward", "onyx", "oodles", "oomph", "opaque", "open", "opera",
    "opiate", "opinion", "optic", "optimal", "orange", "orbit", "orchid",
    "ordeal", "organ", "orient", "origin", "oriole", "ornament", "orphan",
    "oscillate", "osmosis", "osprey", "ostrich", "other", "otter", "ounce",
    "oust", "outbid", "outburst", "outcast", "outcome", "outcry", "outdated",
    "outdo", "outdoor", "outfit", "outflank", "outgoing", "outgrow", "outlast",
    "outlaw", "outlet", "outlive", "outlook", "outpost", "output", "outrage",
    "outrank", "outright", "outset", "outside", "outsize", "outskirt",
    "outsmart", "outsource", "outspoken", "outstrip", "outward", "outwit",
    "oven", "overact", "overall", "overarch", "overboard", "overbook",
    "overcast", "overcoat", "overflow", "overgrown", "overhaul", "overhead",
    "overhear", "overjoy", "overkill", "overlap", "overload", "overlook",
    "overlord", "overmuch", "overnight", "overpass", "overpay", "overrun",
    "oversee", "overshoot", "oversight", "oversize", "overstate", "overt",
    "overtime", "overturn", "overuse", "overview", "owe", "owlet", "owner",
    "oxide", "oxygen", "oyster", "ozone",
    "pace", "pacifist", "package", "pact", "paddle", "padlock", "pagan",
    "pageboy", "pagoda", "pail", "painter", "palace", "palette", "palisade",
    "pamphlet", "pancake", "panda", "pandemic", "pang", "panic", "panorama",
    "panther", "pantry", "pants", "papa", "papaya", "paper", "papoose",
    "paprika", "parade", "paradox", "paraffin", "paragon", "parakeet",
    "parallax", "paramount", "parasol", "parcel", "pardon", "parent",
    "parish", "parka", "parlance", "parody", "parole", "parrot", "parsley",
    "parson", "partake", "partial", "partisan", "passage", "passbook",
    "passion", "passive", "passport", "password", "pasta", "paste", "pastel",
    "pastime", "pastor", "pasture", "patch", "patent", "pathway", "patio",
    "patriarch", "patriot", "patrol", "patron", "pattern", "paunch", "pauper",
    "pause", "pavement", "pavilion", "paw", "payoff", "peace", "peach",
    "peacock", "peanut", "pearl", "pebble", "pecan", "pedagogy", "pedal",
    "pedestal", "pedigree", "peekaboo", "peer", "pelican", "pellet", "pelt",
    "penalty", "pencil", "pendant", "penguin", "penknife", "penny", "pension",
    "pentagon", "pepper", "percale", "percent", "perch", "percolate",
    "perennial", "perfect", "perform", "perfume", "perhaps", "peril",
    "period", "perish", "perjury", "perky", "perm", "permanent", "permit",
    "peroxide", "persist", "person", "perspire", "persuade", "pert",
    "perturb", "pervade", "pessimist", "pest", "petal", "petite", "petrify",
    "petrol", "phalanx", "phantom", "pharmacy", "phase", "philosophy",
    "phoenix", "phone", "photon", "phrase", "physics", "pianist", "pickax",
    "picket", "pickle", "picture", "piece", "pier", "piety", "pigeon",
    "pigment", "pigtail", "pilgrim", "pillar", "pillow", "pilot", "pimp",
    "pinafore", "pincer", "pinhead", "pinkie", "pinnacle", "pinpoint",
    "pint", "pioneer", "pious", "pipeline", "piracy", "pirate", "pistol",
    "piston", "pitcher", "pitchfork", "pitfall", "pithy", "pivot", "pixel",
    "pixie", "pizza", "placebo", "placid", "plague", "plaid", "plain",
    "plan", "plane", "planet", "plank", "plaque", "plaster", "plateau",
    "playboy", "playful", "playhouse", "playpen", "plea", "plead", "pleat",
    "pledge", "plentiful", "plenty", "plethora", "plexus", "pliable", "plight",
    "plod", "plow", "pluck", "plug", "plumage", "plumb", "plume",
    "plunder", "plunge", "plural", "plus", "plush", "pneumatic", "poach",
    "pocket", "podcast", "poem", "poignant", "point", "poise", "polar",
    "polecat", "police", "policy", "polish", "politic", "poll", "pollen",
    "polo", "polygon", "pompano", "poncho", "ponder", "pony", "pool",
    "popcorn", "poplar", "poppy", "populate", "porch", "pore", "porous",
    "portable", "portal", "portico", "portly", "portray", "possess",
    "possum", "postal", "postbox", "poster", "postman", "posture", "potato",
    "potent", "potion", "potluck", "pouch", "pout", "powder", "power",
    "practice", "prairie", "praise", "prance", "prank", "prawn", "preach",
    "precede", "precept", "precinct", "precious", "precise", "predict",
    "preempt", "preen", "prefix", "prelude", "premiere", "premise",
    "premium", "preoccupy", "prep", "presage", "present", "pressing",
    "presto", "presume", "pretend", "pretext", "pretty", "pretzel",
    "prevail", "prevent", "preview", "previous", "prewar", "prey",
    "priceless", "prickle", "pride", "priest", "primal", "primary",
    "primate", "primer", "primp", "princess", "principal", "principle",
    "prior", "prism", "prison", "private", "privet", "prize", "probe",
    "problem", "proceed", "process", "proctor", "prodigy", "produce",
    "profane", "profess", "profile", "profit", "progeny", "program",
    "project", "prologue", "prolong", "promise", "promote", "pronto",
    "proof", "prop", "propane", "propel", "proper", "prophet", "propose",
    "prorate", "prose", "prosper", "protect", "proton", "protract",
    "proud", "proverb", "provide", "prow", "prowl", "proxy", "prude",
    "prudent", "prune", "pry", "psalm", "pseudo", "psyche", "psychic",
    "public", "pucker", "pudding", "puddle", "pueblo", "puff", "pulley",
    "pulp", "pulsar", "pumpkin", "punch", "punctual", "pungent", "punish",
    "punk", "punster", "punt", "pupil", "puppet", "puppy", "purchase",
    "puree", "purge", "purify", "puritan", "purloin", "purple", "purpose",
    "purr", "purse", "pursue", "purvey", "pushcart", "pushover", "pustule",
    "putty", "puzzle", "pygmy", "pyramid", "python",
    "quack", "quadrant", "quail", "quake", "quality", "quantum", "quarrel",
    "quarry", "quarter", "quartet", "quasar", "quash", "quasi", "queasy",
    "queen", "queer", "quell", "query", "quest", "queue", "quick",
    "quiet", "quill", "quilt", "quintet", "quirk", "quit", "quiver",
    "quota", "quote",
    "rabbi", "rabbit", "rabid", "raccoon", "raceway", "radial", "radiant",
    "radiator", "radical", "radio", "radish", "radius", "raffle", "raft",
    "rage", "ragged", "ragweed", "raider", "railroad", "railway",
    "rainbow", "rainfall", "rainy", "raise", "raisin", "raja", "ramble",
    "ramekin", "rampage", "rampart", "ramrod", "ranch", "random", "ranger",
    "ransom", "rapid", "rapture", "rarebit", "rascal", "rasp", "ratchet",
    "rate", "rather", "ratify", "ration", "rattle", "rave", "ravel",
    "raven", "ravine", "rawhide", "razz", "reabsorb", "reach", "react",
    "readjust", "ready", "realism", "reality", "realize", "realm", "ream",
    "reap", "rear", "reason", "rebel", "rebound", "rebuff", "rebuke",
    "rebut", "recall", "recap", "recede", "recent", "recess", "recipe",
    "recital", "reckon", "reclaim", "recline", "recoil", "recopy", "record",
    "recourse", "recover", "recruit", "rectify", "recycle", "redcoat",
    "reddish", "redeem", "redesign", "redhead", "redness", "redo", "redwood",
    "reef", "reek", "reel", "referee", "refill", "refine", "reflect",
    "reform", "refrain", "refresh", "refuge", "refund", "refuse", "refute",
    "regain", "regal", "regard", "regent", "regime", "region", "regret",
    "regular", "rehash", "reign", "reindeer", "reject", "rejoice", "relapse",
    "relate", "release", "relief", "relish", "relive", "rely", "remain",
    "remake", "remark", "remedy", "remind", "remnant", "remorse", "remote",
    "remove", "rename", "render", "renege", "renew", "renovate", "rental",
    "repair", "repeal", "repel", "replace", "replay", "report", "repose",
    "reprieve", "reproach", "reproof", "reptile", "republic", "repulse",
    "repute", "request", "rescue", "resemble", "reserve", "reside", "resign",
    "resist", "resolute", "resolve", "resort", "resource", "respect",
    "response", "restitution", "restive", "restless", "restore", "restrain",
    "result", "retail", "retain", "retard", "retentive", "rethink", "retina",
    "retire", "retort", "retouch", "retrace", "retract", "retreat",
    "retrieve", "retrofit", "return", "reunion", "reveal", "revel",
    "revenge", "revenue", "revere", "reverse", "revert", "review", "revile",
    "revise", "revive", "revoke", "revolt", "revolve", "reword", "rewrite",
    "rhapsody", "rhetoric", "rheumatism", "rhino", "rhubarb", "rhyme",
    "rhythm", "ribald", "ribbon", "riddle", "ridge", "rife", "rifle",
    "rift", "rigatoni", "rightful", "rigid", "rigor", "rinse", "riot",
    "ripe", "ripple", "risk", "ritual", "rival", "river", "rivet",
    "roadbed", "roadway", "roam", "roast", "robot", "robust", "rocket",
    "rodent", "rodeo", "rogue", "role", "rollback", "romance", "romp",
    "roof", "roomful", "root", "rope", "rosette", "rosewood", "roster",
    "rotate", "rotor", "rouge", "rough", "roundup", "route", "routine",
    "rove", "rowboat", "royal", "rubble", "ruckus", "rudder", "ruffle",
    "rugby", "ruin", "rule", "rumba", "rumble", "rummage", "runabout",
    "runner", "runoff", "runway", "rural", "rush", "russet", "rustic",
    "rye",
    "sabbath", "saber", "sable", "sabotage", "sacred", "sadden", "saddle",
    "safari", "safe", "saffron", "saga", "sage", "sailboat", "sailor",
    "saint", "salad", "salami", "salary", "saline", "saliva", "salmon",
    "salon", "salsa", "salt", "salute", "salvage", "salvo", "sampler",
    "sanctify", "sanction", "sanctity", "sanctum", "sandal", "sandbox",
    "sandhog", "sanity", "sapling", "sapphire", "sarcasm", "sash", "satanic",
    "satiate", "satire", "satisfy", "sauce", "saucer", "sauna", "sausage",
    "savage", "savannah", "savior", "savor", "sawdust", "sawmill", "sax",
    "scab", "scaffold", "scalar", "scald", "scallop", "scalp", "scaly",
    "scamper", "scan", "scandal", "scant", "scapegoat", "scarce", "scare",
    "scarf", "scarlet", "scary", "scatter", "scavenger", "scenery", "scenic",
    "scepter", "schedule", "scheme", "scholar", "science", "scissor",
    "scoff", "scold", "scoop", "scooter", "scope", "scorch", "score",
    "scorn", "scotch", "scoundrel", "scour", "scout", "scowl", "scramble",
    "scrape", "scratch", "scrawl", "scream", "screech", "screen", "screw",
    "scribble", "scribe", "scrimmage", "script", "scroll", "scrooge",
    "scrub", "scruffy", "scruple", "sculpt", "scum", "scurvy", "scythe",
    "seafood", "seagull", "seal", "seam", "seaport", "search", "seashore",
    "seaside", "season", "seat", "seaweed", "secede", "seclude", "second",
    "secret", "sect", "section", "secular", "secure", "sedan", "sedate",
    "sediment", "seduce", "seed", "seemly", "seesaw", "seethe", "segment",
    "seismic", "seize", "select", "selfish", "sellout", "seltzer", "seminar",
    "senate", "senator", "senile", "sense", "sensor", "sentence", "sepia",
    "septic", "sequel", "sequin", "serene", "serf", "sergeant", "serial",
    "sermon", "serpent", "servant", "session", "setback", "settle", "seven",
    "sever", "sewage", "shabby", "shackle", "shade", "shadow", "shady",
    "shaft", "shaggy", "shaker", "shallow", "sham", "shamble", "shame",
    "shampoo", "shanty", "shape", "shard", "share", "shark", "sharp",
    "shatter", "shave", "shawl", "sheaf", "shear", "sheath", "shed",
    "sheen", "sheepskin", "shekel", "shelter", "shepherd", "sherbet",
    "sheriff", "shield", "shift", "shin", "shine", "shingle", "shiny",
    "shipment", "shirt", "shiver", "shoal", "shock", "shoehorn", "shoelace",
    "shop", "shore", "shortage", "shorten", "shorthand", "shortsighted",
    "shoulder", "shout", "shove", "showcase", "showdown", "shower",
    "shrapnel", "shred", "shrewd", "shriek", "shrill", "shrimp", "shrine",
    "shrink", "shrivel", "shroud", "shrub", "shrug", "shuck", "shudder",
    "shuffle", "shun", "shunt", "shush", "shuttle", "sibling", "sickle",
    "sideline", "sidewalk", "siege", "sierra", "sieve", "sift", "sigh",
    "sight", "sigma", "signal", "signet", "signify", "signpost", "silence",
    "silhouette", "silica", "silicon", "silkworm", "silo", "silver",
    "similar", "simile", "simmer", "simple", "simulate", "sincere", "sinew",
    "sinful", "singe", "single", "sinus", "siphon", "sirloin", "sister",
    "situate", "sixty", "sizable", "skate", "skeet", "skeleton", "skeptic",
    "sketch", "skewer", "skiff", "skillet", "skillful", "skim", "skimp",
    "skin", "skip", "skirmish", "skirt", "skit", "skull", "skunk",
    "skyline", "slab", "slack", "slake", "slam", "slander", "slang",
    "slant", "slate", "slaughter", "slave", "sled", "sleek", "sleep",
    "sleet", "sleeve", "sleigh", "slender", "slice", "slick", "slide",
    "sling", "slingshot", "slip", "slit", "slither", "sliver", "slogan",
    "slop", "slosh", "slot", "slouch", "slow", "sludge", "slug",
    "slum", "slump", "slur", "sly", "smack", "smallpox", "smart",
    "smear", "smelt", "smile", "smirk", "smithy", "smog", "smoke",
    "smooth", "smudge", "smug", "snack", "snag", "snail", "snapshot",
    "snare", "snarl", "sneak", "sneer", "sniff", "snipe", "snivel",
    "snoop", "snore", "snort", "snow", "snub", "snuff", "snug",
    "soak", "soap", "soar", "sober", "soccer", "social", "socket",
    "sod", "soda", "sofa", "softball", "soften", "software", "soggy",
    "solar", "solder", "solemn", "solicit", "solid", "solo", "solstice",
    "solution", "solvent", "somber", "somebody", "somehow", "somersault",
    "somewhat", "sonar", "sonata", "songbird", "sonic", "sonnet", "soothe",
    "sooty", "sophomore", "soprano", "sorbet", "sorcery", "sorrow", "sortie",
    "souffle", "sought", "sound", "soup", "sour", "source", "southpaw",
    "souvenir", "soybean", "spa", "space", "spade", "spaghetti", "span",
    "spandex", "spare", "spark", "sparrow", "spasm", "spatula", "spawn",
    "speaker", "spear", "special", "species", "specify", "speck", "spectacle",
    "spectrum", "speech", "speed", "spell", "spelunker", "spend", "sphere",
    "sphinx", "spice", "spider", "spike", "spinach", "spindle", "spine",
    "spiral", "spirit", "spiteful", "splash", "spleen", "splendor", "splice",
    "splint", "splinter", "spoil", "sponge", "sponsor", "spoof", "spook",
    "spool", "spoon", "spore", "sport", "spouse", "spout", "sprawl",
    "spread", "spring", "sprinkle", "sprout", "spruce", "spry", "spur",
    "spurt", "sputter", "spy", "squabble", "squad", "squall", "squalor",
    "squander", "square", "squash", "squawk", "squeak", "squeal", "squeegee",
    "squeeze", "squelch", "squid", "squint", "squirm", "squirrel", "squirt",
    "stable", "stadium", "staff", "stage", "stair", "stake", "stale",
    "stammer", "stampede", "stance", "stand", "stanza", "staple", "starboard",
    "starch", "stare", "starfish", "stark", "starry", "startle", "starve",
    "stash", "state", "static", "station", "statue", "status", "statute",
    "staunch", "stave", "stay", "steady", "steak", "stealth", "steam",
    "steel", "steep", "steer", "stellar", "stem", "stench", "stencil",
    "stepchild", "stereo", "sterile", "sterling", "stern", "steward",
    "stick", "stifle", "stigma", "still", "stilt", "stimuli", "stingy",
    "stipend", "stirrup", "stitch", "stockade", "stocking", "stockpile",
    "stodgy", "stoic", "stoke", "stomach", "stoneware", "stoop", "stopgap",
    "storage", "store", "stork", "storm", "stout", "stove", "stow",
    "straggle", "straight", "strain", "strait", "strange", "strata",
    "strategy", "straw", "stray", "streak", "stream", "street", "stress",
    "stretch", "strew", "strict", "stride", "strife", "strike", "string",
    "stripe", "strive", "stroke", "stroll", "strong", "strudel", "struggle",
    "strut", "stub", "stucco", "student", "studio", "study", "stuff",
    "stumble", "stump", "stun", "stunt", "stupor", "sturdy", "stutter",
    "stylish", "stylist", "stylus", "suave", "subdue", "subject", "sublet",
    "sublime", "submarine", "submit", "subpar", "subplot", "subside",
    "subsidy", "subsist", "subsoil", "substance", "subsume", "subtle",
    "subtract", "suburb", "subvert", "subway", "succeed", "succumb",
    "suckle", "suction", "sudden", "suffer", "suffice", "suffix", "suffrage",
    "sugar", "suicide", "suitcase", "sulfur", "sulk", "sullen", "sultan",
    "sumac", "summary", "summer", "summit", "summon", "sump", "sunburn",
    "sundae", "sundial", "sunfish", "sunflower", "sunk", "sunlight",
    "sunrise", "sunset", "suntan", "superb", "superficial", "superhighway",
    "superior", "supermarket", "supine", "supper", "supply", "support",
    "suppose", "suppress", "supreme", "surety", "surf", "surgeon", "surname",
    "surprise", "surrender", "surround", "survey", "survival", "survivor",
    "suspect", "suspend", "sustain", "swab", "swagger", "swallow", "swamp",
    "swan", "swap", "swarm", "swatch", "swath", "swear", "sweat",
    "sweater", "sweep", "sweet", "swell", "swept", "swerve", "swift",
    "swim", "swindle", "swing", "swipe", "swirl", "switch", "swivel",
    "swollen", "swoon", "swoop", "sword", "sycamore", "syllable", "symbol",
    "synapse", "syndrome", "synopsis", "syntax", "syrup", "system",
    "tabernacle", "tablet", "taboo", "tackle", "tactic", "taffy", "tailspin",
    "takeoff", "talent", "talkie", "tallow", "tally", "talon", "tamale",
    "tamarind", "tame", "tamper", "tandem", "tangible", "tangle", "tango",
    "tankful", "tanker", "tannery", "tapioca", "target", "tariff", "tarmac",
    "tarnish", "tarot", "tart", "task", "tassel", "taste", "tattle",
    "tattoo", "taunt", "tavern", "taxi", "tByte", "teacup", "teammate",
    "teapot", "teardrop", "teaspoon", "technique", "tedious", "teem",
    "teenage", "telegram", "telephone", "telescope", "telex", "teller",
    "temper", "tempest", "temple", "tempo", "tempt", "tenant", "tendency",
    "tender", "tenement", "tenet", "tennis", "tenor", "tension", "tentacle",
    "tenuous", "tenure", "terminal", "terrace", "terrain", "terrible",
    "terrier", "terrify", "territory", "terror", "testify", "tetanus",
    "tether", "textile", "texture", "thank", "thatch", "thaw", "theater",
    "theft", "theme", "thereof", "thermal", "thesaurus", "thesis", "thicken",
    "thicket", "thief", "thigh", "thimble", "thinly", "thirst", "thirty",
    "thistle", "thong", "thorax", "thorn", "thorough", "thousand", "thrall",
    "thread", "threat", "threefold", "thrift", "thrill", "thrive", "throat",
    "throb", "throne", "throttle", "through", "throw", "thrush", "thrust",
    "thug", "thumb", "thump", "thunder", "thwart", "thyme", "tiara",
    "ticket", "tickle", "tide", "tidy", "tight", "tile", "tillable",
    "timber", "timeout", "timer", "timid", "tinderbox", "tinfoil", "tingle",
    "tinker", "tinkle", "tinsel", "tint", "tiptoe", "tirade", "tissue",
    "titanium", "title", "toadstool", "toast", "tobacco", "today", "toe",
    "toenail", "toffee", "together", "toil", "toilet", "token", "toll",
    "tomahawk", "tomato", "tombstone", "tonal", "tong", "tonight", "tonsil",
    "tooth", "topaz", "topic", "topmast", "topple", "torch", "torment",
    "tornado", "torpedo", "torque", "torrent", "torso", "tortilla", "tortoise",
    "torture", "toss", "totter", "touch", "tough", "tourist", "tourney",
    "towboat", "towel", "tower", "township", "toxic", "toxin", "toy",
    "trace", "track", "tract", "trade", "traffic", "tragic", "trail",
    "traitor", "trample", "trance", "tranquil", "transfer", "transform",
    "transit", "transmit", "trapdoor", "trapeze", "trauma", "travel",
    "traverse", "trawler", "treadmill", "treason", "treasure", "treaty",
    "treble", "tree", "trek", "tremble", "tremor", "trench", "trend",
    "trespass", "trestle", "trial", "tribal", "tribune", "tribute", "trick",
    "tricycle", "trifle", "trigger", "trill", "trilogy", "trim", "trinket",
    "triple", "tripod", "trite", "triumph", "trivial", "troll", "trolley",
    "trombone", "trooper", "trophy", "tropical", "trouble", "trouser",
    "truce", "truck", "trudge", "trumpet", "trunk", "trustee", "tsunami",
    "tub", "tuba", "tubular", "tuck", "tugboat", "tuition", "tulip",
    "tumble", "tumor", "tundra", "tune", "tunic", "tunnel", "turban",
    "turbine", "turbo", "turf", "turmoil", "turnip", "turnkey", "turret",
    "turtle", "tusk", "tutor", "tutu", "tuxedo", "twang", "tweak",
    "tweed", "twice", "twig", "twilight", "twinge", "twinkle", "twirl",
    "twist", "twitch", "tycoon", "typhoon", "tyrant",
    "ulcer", "ultimate", "ultra", "umbrella", "umpire", "unable", "unaware",
    "unbeaten", "unbiased", "unbroken", "uncommon", "uncouth", "underact",
    "underage", "underarm", "undercoat", "undercut", "underdog", "underfoot",
    "undergo", "undergrad", "underlay", "underlip", "underpay", "underpin",
    "undersea", "undertake", "undertow", "underwear", "undo", "undue",
    "undulate", "unearth", "uneasy", "unequal", "unfair", "unfit",
    "unfold", "unfreeze", "ungodly", "unhappy", "unhealthy", "unhinge",
    "unhitch", "unhook", "unhurt", "unicorn", "unicycle", "uniform",
    "unipolar", "unique", "unison", "universe", "unjust", "unkempt",
    "unknown", "unlace", "unleash", "unlisted", "unload", "unlock", "unloose",
    "unlucky", "unmanly", "unmask", "unmoved", "unpack", "unpaid", "unplug",
    "unravel", "unreal", "unrest", "unripe", "unroll", "unsaddle", "unscrew",
    "unseal", "unseat", "unsettle", "unshaken", "unskilled", "unsnap",
    "unsnarl", "unsound", "unspoken", "unstable", "unsteady", "unstop",
    "unstuck", "untidy", "untie", "until", "untimely", "unto", "untold",
    "unusual", "unveil", "unwary", "unwell", "unwind", "unwise", "unwound",
    "unwrap", "unyoke", "upbeat", "upbringing", "upchuck", "update",
    "upend", "upgrade", "upheaval", "upheld", "uphill", "uphold", "upland",
    "uplift", "upload", "upon", "upper", "upright", "uprising", "uproar",
    "uproot", "upset", "upshot", "upside", "upstage", "upstream", "uptake",
    "uptight", "uptown", "upturn", "upward", "upwind", "uranium", "urban",
    "urchin", "urgent", "urine", "usable", "usage", "usher", "usual",
    "utensil", "utmost", "utopia", "utter",
    "vacant", "vaccine", "vacuum", "vagrant", "vague", "vain", "valet",
    "valid", "valley", "valve", "vampire", "vanilla", "vantage", "vapid",
    "vapor", "variant", "varnish", "vary", "vast", "vat", "vault",
    "vector", "veer", "vegetable", "vegetate", "vehicle", "velcro", "velvet",
    "vendor", "veneer", "venerate", "venom", "vent", "venue", "verbose",
    "verdict", "verge", "verify", "vermin", "verse", "version", "vessel",
    "vestige", "veto", "viable", "vibrant", "vibrate", "vice", "victim",
    "victory", "video", "view", "vigesimal", "vigor", "village", "vinegar",
    "vineyard", "vinyl", "viola", "violate", "violent", "viper", "virgin",
    "virtual", "virtue", "visa", "visible", "vision", "visitor", "visual",
    "vital", "vivid", "vocal", "vodka", "vogue", "voice", "volatile",
    "volcano", "volley", "voltage", "volume", "voodoo", "vortex", "vote",
    "vouch", "vowel", "voyage", "vulgar",
    "wad", "wafer", "waffle", "wage", "wagon", "waist", "waiter",
    "waiver", "wakeful", "walkout", "wallaby", "wallet", "walnut", "walrus",
    "wampum", "wander", "wanting", "wanton", "warbler", "warden", "warfare",
    "warhead", "warlike", "warmth", "warning", "warp", "warrant", "warrior",
    "warship", "washbowl", "washout", "wasp", "waste", "watchdog", "watchman",
    "waterfall", "waterfowl", "waterlog", "watermark", "waterway", "watt",
    "wave", "waver", "waxen", "wayfarer", "waylaid", "wayside", "weaken",
    "wealth", "weapon", "wear", "weasel", "weather", "weaver", "webcast",
    "wedding", "wedge", "wedlock", "weekday", "weeble", "weep", "weigh",
    "weight", "weirdo", "welcome", "welfare", "wellbeing", "western",
    "westward", "wetland", "whack", "whale", "wharf", "wheat", "wheel",
    "wheeze", "whereby", "whiff", "while", "whim", "whimper", "whine",
    "whinny", "whip", "whirl", "whisk", "whisper", "whistle", "whiten",
    "whittle", "whiz", "whoa", "whodunit", "whoopee", "whoosh", "wick",
    "widen", "widget", "widow", "width", "wield", "wifi", "wiggle",
    "wildcat", "wilful", "willow", "wimp", "windfall", "windmill", "window",
    "windpipe", "windsurf", "windward", "wine", "wing", "wink", "winner",
    "winter", "wipe", "wishbone", "wisteria", "witch", "withdraw", "wither",
    "within", "without", "witness", "wizard", "wobble", "woe", "wolf",
    "wolverine", "wombat", "wonder", "woodchuck", "woodland", "woodpecker",
    "woodwind", "wool", "word", "workman", "world", "worm", "worry",
    "worship", "worthy", "wound", "woven", "wrack", "wrath", "wreath",
    "wreckage", "wrench", "wrestle", "wretch", "wring", "wrinkle", "wrist",
    "wrong", "xenon", "xerox", "xray", "xylophone",
    "yacht", "yam", "yard", "yarn", "yawn", "yearly", "yeast",
    "yell", "yellow", "yeoman", "yield", "yodel", "yogurt", "yonder",
    "young", "youth", "zany", "zeal", "zebra", "zenith", "zephyr",
    "zero", "zest", "zigzag", "zilch", "zipper", "zircon", "zone",
    "zoom", "zucchini",
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class PasswordConfig:
    """Configuration for password and passphrase generation."""

    length: int = 16
    use_uppercase: bool = True
    use_lowercase: bool = True
    use_digits: bool = True
    use_symbols: bool = True
    exclude_ambiguous: bool = False
    word_count: int = 4
    delimiter: str = "-"


# ---------------------------------------------------------------------------
# Character-set helpers
# ---------------------------------------------------------------------------

# Standard character pools
_UPPERCASE = string.ascii_uppercase        # A-Z
_LOWERCASE = string.ascii_lowercase        # a-z
_DIGITS = string.digits                    # 0-9
_SYMBOLS = "!@#$%^&*()_+-=[]{}|;:,.<>?/~`"


def get_allowed_chars(config: PasswordConfig) -> str:
    """Build the current allowed-character string based on *config*."""
    parts: List[str] = []
    if config.use_uppercase:
        parts.append(_UPPERCASE)
    if config.use_lowercase:
        parts.append(_LOWERCASE)
    if config.use_digits:
        parts.append(_DIGITS)
    if config.use_symbols:
        parts.append(_SYMBOLS)

    allowed = "".join(parts)

    if config.exclude_ambiguous:
        # Remove characters that look alike: 0 O 1 l I
        allowed = "".join(ch for ch in allowed if ch not in AMBIGUOUS_CHARACTERS)

    return allowed


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_password(config: PasswordConfig) -> str:
    """Generate a single password using **secrets.choice** over the allowed set."""
    allowed = get_allowed_chars(config)
    if not allowed:
        raise ValueError("Cannot generate password: no character sets enabled.")
    return "".join(secrets.choice(allowed) for _ in range(config.length))


def generate_passphrase(config: PasswordConfig, wordlist: List[str]) -> str:
    """Generate a single passphrase by picking random words."""
    if config.word_count < 1:
        raise ValueError("Word count must be at least 1.")
    words = [secrets.choice(wordlist) for _ in range(config.word_count)]
    return config.delimiter.join(words)


# ---------------------------------------------------------------------------
# Strength rating
# ---------------------------------------------------------------------------

def rate_password(password: str, config: PasswordConfig) -> Tuple[int, str]:
    """
    Return (entropy_bits, label) for a password.

    Entropy = len(password) * log2(size_of_allowed_set)
    """
    allowed = get_allowed_chars(config)
    if not allowed:
        return (0, "weak")
    pool_size = len(allowed)
    entropy = len(password) * math.log2(pool_size)
    label = _entropy_label(entropy)
    return (int(round(entropy)), label)


def rate_passphrase(word_count: int, wordlist_size: int) -> Tuple[int, str]:
    """
    Return (entropy_bits, label) for a passphrase.

    Entropy = word_count * log2(wordlist_size)
    """
    entropy = word_count * math.log2(wordlist_size)
    label = _entropy_label(entropy)
    return (int(round(entropy)), label)


def _entropy_label(entropy: float) -> str:
    """Map entropy (bits) to a human-readable strength label."""
    if entropy < 50:
        return "weak"
    elif entropy < 70:
        return "medium"
    elif entropy < 100:
        return "strong"
    else:
        return "very strong"


# ---------------------------------------------------------------------------
# Pretty-printing helpers
# ---------------------------------------------------------------------------

def print_password_result(index: int, password: str, config: PasswordConfig) -> None:
    """Print one generated password with index and strength rating."""
    ent, label = rate_password(password, config)
    print(f"  [{index}] {password}")
    print(f"      entropy: ~{ent} bits  →  {label}")


def print_passphrase_result(index: int, passphrase: str, config: PasswordConfig) -> None:
    """Print one generated passphrase with index and strength rating."""
    ent, label = rate_passphrase(config.word_count, len(WORDS))
    print(f"  [{index}] {passphrase}")
    print(f"      entropy: ~{ent} bits  →  {label}")


def print_config(config: PasswordConfig) -> None:
    """Display current configuration."""
    print("─" * 40)
    print(" Current Configuration")
    print("─" * 40)
    print(f"  Length:             {config.length}")
    print(f"  Uppercase:          {'on' if config.use_uppercase else 'off'}")
    print(f"  Lowercase:          {'on' if config.use_lowercase else 'off'}")
    print(f"  Digits:             {'on' if config.use_digits else 'off'}")
    print(f"  Symbols:            {'on' if config.use_symbols else 'off'}")
    print(f"  Exclude ambiguous:  {'on' if config.exclude_ambiguous else 'off'}")
    print(f"  Word count:         {config.word_count}")
    print(f"  Delimiter:          '{config.delimiter}'")
    print("─" * 40)


def print_help() -> None:
    """Print help text."""
    print("Available commands:")
    print("  length <num>                     Set password length (1-256)")
    print("  uppercase on|off|toggle          Toggle uppercase letters")
    print("  lowercase on|off|toggle          Toggle lowercase letters")
    print("  digits on|off|toggle             Toggle digits")
    print("  symbols on|off|toggle            Toggle symbols")
    print("  ambiguous on|off|toggle          Toggle ambiguous-char exclusion")
    print("  generate [N]                     Generate N passwords (default 1)")
    print("  passphrase [N] [words]           Generate N passphrases (word count optional)")
    print("  words <num>                      Set passphrase word count")
    print("  delimiter <char>                 Set passphrase delimiter")
    print("  config                           Show current configuration")
    print("  help                             Show this message")
    print("  quit | exit                      Exit the program")


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

def _parse_bool_toggle(current: bool, arg: str) -> bool:
    """Parse on/off/toggle relative to *current*."""
    arg = arg.strip().lower()
    if arg == "on":
        return True
    elif arg == "off":
        return False
    elif arg == "toggle":
        return not current
    else:
        raise ValueError(f"Expected 'on', 'off', or 'toggle', got '{arg}'")


def repl() -> None:
    """Run the interactive read-eval-print loop."""
    config = PasswordConfig()
    wordlist = WORDS

    print("=" * 60)
    print("  Password Generator  —  type 'help' for commands")
    print("=" * 60)
    print()

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()
        args = parts[1:]

        # ── quit / exit ──
        if cmd in ("quit", "exit"):
            print("Goodbye!")
            break

        # ── help ──
        elif cmd == "help":
            print_help()

        # ── config ──
        elif cmd == "config":
            print_config(config)

        # ── length ──
        elif cmd == "length":
            if not args:
                print("Error: 'length' requires a number, e.g. 'length 20'")
                continue
            try:
                val = int(args[0])
                if val < 1 or val > 256:
                    print("Error: length must be between 1 and 256")
                    continue
                config.length = val
                print(f"Password length set to {val}")
            except ValueError:
                print(f"Error: invalid number '{args[0]}'")

        # ── words (passphrase word count) ──
        elif cmd == "words":
            if not args:
                print("Error: 'words' requires a number, e.g. 'words 6'")
                continue
            try:
                val = int(args[0])
                if val < 1 or val > 50:
                    print("Error: word count must be between 1 and 50")
                    continue
                config.word_count = val
                print(f"Passphrase word count set to {val}")
            except ValueError:
                print(f"Error: invalid number '{args[0]}'")

        # ── delimiter ──
        elif cmd == "delimiter":
            if not args:
                print("Error: 'delimiter' requires a character, e.g. 'delimiter -'")
                continue
            config.delimiter = args[0]
            print(f"Passphrase delimiter set to '{args[0]}'")

        # ── uppercase / lowercase / digits / symbols ──
        elif cmd in ("uppercase", "lowercase", "digits", "symbols"):
            if not args:
                print(f"Error: '{cmd}' requires on, off, or toggle")
                continue
            attr = f"use_{cmd}"
            try:
                new_val = _parse_bool_toggle(getattr(config, attr), args[0])
                setattr(config, attr, new_val)
                status = "on" if new_val else "off"
                print(f"{cmd.capitalize()}: {status}")
            except ValueError as e:
                print(f"Error: {e}")

        # ── ambiguous ──
        elif cmd == "ambiguous":
            if not args:
                print("Error: 'ambiguous' requires on, off, or toggle")
                continue
            try:
                new_val = _parse_bool_toggle(config.exclude_ambiguous, args[0])
                config.exclude_ambiguous = new_val
                status = "on" if new_val else "off"
                print(f"Exclude ambiguous characters: {status}")
            except ValueError as e:
                print(f"Error: {e}")

        # ── generate ──
        elif cmd == "generate":
            count = 1
            if args:
                try:
                    count = int(args[0])
                    if count < 1 or count > 100:
                        print("Error: count must be between 1 and 100")
                        continue
                except ValueError:
                    print(f"Error: invalid number '{args[0]}'")
                    continue

            # Check that at least one character set is enabled
            allowed = get_allowed_chars(config)
            if not allowed:
                print("Cannot generate password: no character sets enabled.")
                continue

            for i in range(1, count + 1):
                pwd = generate_password(config)
                print_password_result(i, pwd, config)

        # ── passphrase ──
        elif cmd == "passphrase":
            count = 1
            saved_word_count = config.word_count

            # Parse optional N and word count
            if args:
                try:
                    count = int(args[0])
                    if count < 1 or count > 100:
                        print("Error: count must be between 1 and 100")
                        continue
                except ValueError:
                    print(f"Error: invalid number '{args[0]}'")
                    continue
                if len(args) >= 2:
                    try:
                        wc = int(args[1])
                        if wc < 1 or wc > 50:
                            print("Error: word count must be between 1 and 50")
                            continue
                        config.word_count = wc
                    except ValueError:
                        print(f"Error: invalid word count '{args[1]}'")
                        continue

            for i in range(1, count + 1):
                pp = generate_passphrase(config, wordlist)
                print_passphrase_result(i, pp, config)

            # Restore word count if temporarily overridden
            if len(args) >= 2:
                config.word_count = saved_word_count

        # ── unknown ──
        else:
            print(f"Unknown command: '{cmd}'. Type 'help' for available commands.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    repl()
