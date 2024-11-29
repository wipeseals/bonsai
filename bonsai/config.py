import os
from amaranth import Shape, unsigned
from amaranth.utils import exact_log2

# TODO: dataclassで撒いていたが、Variable Annotation での定義時に参照できず相性が悪いのでglobalに移動している
#       Componentのsuper().__init__()で定義しても良かったが、あまりきれいではなかったので一旦保留している

#####################################################
# environment variables

# Directory for generated files
DIST_FILE_DIR: str = "dist"


def dist_file_path(file_name: str) -> str:
    """
    Get the path of the generated file
    """

    if not os.path.exists(DIST_FILE_DIR):
        os.makedirs(DIST_FILE_DIR)
    return f"{DIST_FILE_DIR}/{file_name}"


#####################################################
# CPU Register and Memory Configuration (values)

# Register width (RV32 or RV64 or RV128)
REG_WIDTH: int = 32

# Memory address width (RV32 or RV64 or RV128)
ADDR_WIDTH: int = 32

# Memory data width
DATA_WIDTH: int = 32

# Instruction width (reserved for future use)
INST_WIDTH: int = 32

# Instruction byte width (Compress=2byte, RV32=4byte, RV64=8byte)
INST_BYTES: int = INST_WIDTH // 8

# Bitshift for PC to get the instruction address (Compress=1, RV32=2, RV64=3)
INST_ADDR_SHIFT: int = exact_log2(INST_BYTES)

# Number of general purpose registers
NUM_GPR: int = 32

# Number of floating point registers
NUM_FPR: int = 32

# Number of register file index (gpr + fpr)
NUM_REGFILE_INDEX: int = NUM_GPR + NUM_FPR

# Number of gpr and fpr registers
REFGILE_INDEX_WIDTH: int = exact_log2(NUM_REGFILE_INDEX)

# opcode width
OPCODE_WIDTH: int = 7

#####################################################
# CPU Register and Memory Configuration (shapes)

# Register shape
REG_SHAPE: Shape = unsigned(REG_WIDTH)

# Memory address shape
ADDR_SHAPE: Shape = unsigned(ADDR_WIDTH)

# Memory data shape
DATA_SHAPE: Shape = unsigned(DATA_WIDTH)

# Instruction shape
INST_SHAPE: Shape = unsigned(INST_WIDTH)

# general purpose register shape
GPR_SHAPE: Shape = unsigned(REG_WIDTH)

# register index shape (gpr + fpr)
REGFILE_INDEX_SHAPE: Shape = unsigned(REFGILE_INDEX_WIDTH)

# opcode shape
OPCODE_SHAPE: Shape = unsigned(OPCODE_WIDTH)

#####################################################
# L1 Cache Configuration

# Cache Memory Depth
L1_CACHE_DEPTH: int = 256
