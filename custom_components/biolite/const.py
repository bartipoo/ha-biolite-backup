"""Constants for the BioLite Backup integration."""

DOMAIN = "biolite"

BASE_URL = "https://p2i1vul85i.execute-api.us-west-1.amazonaws.com/dev"
LOGIN_PATH = "/v1/login2"
NODES_PATH = "/v1/user/nodes"
STATUS_PATH = "/v1/user/nodes/status"
PARAMS_PATH = "/v1/user/nodes/params"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"

DEFAULT_SCAN_INTERVAL = 60

# Field IDs confirmed by diffing real device-state samples against the
# BioLite app's displayed values (see project notes) -- not from any
# official schema, since BioLite exposes this as a single opaque string.
FIELD_SOC = 0x09          # state of charge, 0.0-1.0 fraction
FIELD_TEMPERATURE = 0x1b  # degrees C
FIELD_CAPACITY = 0x13     # rated capacity, Wh (block 1 / Core only)

# The two repeated name-blob groups in the blob; block 1 carries the Core
# unit's own stages, block 4 carries the attached Extend battery's stages.
BLOCK_CORE = "core"
BLOCK_EXTEND = "extend"

POWER_STAGE_NAMES = ("dcdc_link", "dcdc_mppt", "ac_out", "ac_in", "gate_link")
