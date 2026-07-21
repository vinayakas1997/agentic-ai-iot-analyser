import random

_ADJECTIVES = [
    "Amber", "Azure", "Beryl", "Bronze", "Cerulean", "Cobalt", "Copper", "Coral",
    "Crimson", "Emerald", "Golden", "Indigo", "Ivory", "Jade", "Jet", "Lapis",
    "Lilac", "Lunar", "Mauve", "Ochre", "Onyx", "Opal", "Platinum", "Rose",
    "Ruby", "Sapphire", "Scarlet", "Silver", "Slate", "Solar", "Steel", "Teal",
    "Topaz", "Violet", "Viridian", "Aegean", "Boreal", "Cosmic", "Crystal",
    "Dawn", "Dusk", "Eagle", "Echo", "Falcon", "Frost", "Ghost", "Haven",
    "Horizon", "Iris", "Kestrel", "Meadow", "Meridian", "Monarch", "Nebula",
    "Nova", "Obsidian", "Orion", "Pebble", "Perseus", "Pulse", "Quantum",
    "Quartz", "Radar", "Raven", "Ripple", "Sage", "Satin", "Shade", "Shadow",
    "Silk", "Solstice", "Static", "Stellar", "Storm", "Summit", "Sunbeam",
    "Swallow", "Talon", "Thunder", "Tide", "Timber", "Titan", "Tracer",
    "Twilight", "Umbra", "Vector", "Vega", "Vellum", "Velvet", "Vertex",
    "Vortex", "Warp", "Wave", "Weaver", "Wisp", "Zenith", "Zephyr",
]

_NOUNS = [
    "Aegis", "Anchor", "Archive", "Aria", "Atlas", "Axiom", "Badge", "Banner",
    "Basin", "Beacon", "Bloom", "Braid", "Breaker", "Bridge", "Bristle", "Buffer",
    "Canvas", "Cascade", "Caster", "Circuit", "Clarity", "Compass", "Cradle",
    "Crest", "Cursor", "Cycle", "Dapple", "Delta", "Diorama", "Diode", "Domain",
    "Dynasty", "Eddy", "Effigy", "Ember", "Engine", "Equinox", "Facet", "Filter",
    "Flange", "Flare", "Flow", "Flume", "Forge", "Fractal", "Frame", "Fringe",
    "Fusion", "Gadget", "Gateway", "Gemma", "Gimbal", "Glacier", "Glider", "Grove",
    "Harbor", "Harmony", "Harness", "Hearth", "Helix", "Hinge", "Hollow", "Hybrid",
    "Impulse", "Ingot", "Inlay", "Inlet", "Jigsaw", "Journal", "Keystone", "Knoll",
    "Labyrinth", "Lagoon", "Lantern", "Lattice", "Legacy", "Lens", "Lever", "Loom",
    "Lumen", "Lynx", "Matrix", "Membrane", "Mesa", "Mimic", "Mirror",
    "Module", "Mosaic", "Nexus", "Niche", "Nimbus", "Oasis", "Ocular", "Oracle",
    "Orbit", "Oscillator", "Outpost", "Palisade", "Paradox", "Paragon", "Parlor",
    "Particle", "Pavilion", "Peak", "Phantom", "Pinnacle", "Pipeline", "Piston",
    "Plane", "Plateau", "Plume", "Portal", "Prism", "Prowl", "Pulsar", "Pylon",
    "Pyre", "Radius", "Reactor", "Reef", "Relay", "Ridge", "Ripple", "Rotor",
    "Router", "Scepter", "Scout", "Sentry", "Shard", "Shelf", "Shield", "Shingle",
    "Shore", "Signal", "Siphon", "Sniper", "Socket", "Solenoid", "Sonar", "Spire",
    "Spoke", "Spool", "Sprocket", "Stable", "Stator", "Stencil", "Strand", "Studio",
    "Summit", "Surge", "Switch", "Symbol", "Tableau", "Talon", "Temple", "Tensor",
    "Throttle", "Tide", "Timber", "Tracer", "Trail", "Tram", "Treble", "Trench",
    "Trigger", "Troop", "Tunnel", "Turbine", "Twine", "Valve", "Vault", "Veil",
    "Venture", "Vessel", "Vestige", "Viaduct", "Vista", "Volt", "Vortex", "Ward",
    "Watch", "Weave", "Wharf", "Widget", "Wicket", "Wreath", "Yard", "Yield",
    "Zenith", "Zone",
]


def generate_session_name() -> str:
    return f"{random.choice(_ADJECTIVES)} {random.choice(_NOUNS)}"
