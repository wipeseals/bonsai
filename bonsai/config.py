from amaranth import Shape, unsigned


# TODO: dataclassで撒いていたが、Variable Annotation での定義時に参照できず相性が悪いのでglobalに移動している
#       Componentのsuper().__init__()で定義しても良かったが、あまりきれいではなかったので一旦保留している

# Register width (RV32 or RV64 or RV128)
REG_WIDTH: int = 32

# Memory address width (RV32 or RV64 or RV128)
ADDR_WIDTH: int = 32

# Memory data width
DATA_WIDTH: int = 32

# Instruction width (reserved for future use)
INST_WIDTH: int = 32


# Register shape
REG_SHAPE: Shape = unsigned(REG_WIDTH)

# Memory address shape
ADDR_SHAPE: Shape = unsigned(ADDR_WIDTH)

# Memory data shape
DATA_SHAPE: Shape = unsigned(DATA_WIDTH)

# Instruction shape
INST_SHAPE: Shape = unsigned(INST_WIDTH)
