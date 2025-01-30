from typing import Literal, Optional

import pydantic
from amaranth import Module
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from pydantic.dataclasses import dataclass


@dataclass
class WishboneTag:
    """
    WishboneTag is a data class that represents a Wishbone tag with specified name, operation, tag type, and width.
    Attributes:
        name (str): The name of the tag.
        operation (str): The operation of the tag.
        tagtype (WishboneTagType): The type of the tag.
        width (int): The width of the tag.
    """

    name: str
    operation: str
    width: int


@dataclass
class WishboneSpec:
    """
    WishboneSpec is a data class that represents a Wishbone bus specification with specified port size, granularity, spec revision, error support, retry support, tag support, and endianness.
    Attributes:
        port_size (Literal[8, 16, 32, 64]): The size of the Wishbone port.
        granularity (Optional[Literal[8, 16, 32, 64]]): The granularity of the Wishbone bus.
        spec_rev (str): The revision of the Wishbone specification.
        support_err_i (bool): Whether error support is enabled.
        support_rty_i (bool): Whether retry support is enabled.
        support_tga_o (Optional[WishboneTag]): The tag support for the address bus.
        support_tgd_i (Optional[WishboneTag]): The tag support for the data input bus.
        support_tgd_o (Optional[WishboneTag]): The tag support for the data output bus.
        support_tgc_o (Optional[WishboneTag]): The tag support for the cycle bus.
        endian (Optional[Literal["little", "big"]]): The endianness of the Wishbone bus.
    """

    port_size: Literal[8, 16, 32, 64]
    granularity: Optional[Literal[8, 16, 32, 64]] = None
    spec_rev: str = "B4"
    support_err_i: bool = False
    support_rty_i: bool = False
    support_tga_o: Optional[WishboneTag] = None
    support_tgd_i: Optional[WishboneTag] = None
    support_tgd_o: Optional[WishboneTag] = None
    support_tgc_o: Optional[WishboneTag] = None
    endian: Optional[Literal["little", "big"]] = None

    def __post_init_post_parse__(self):
        # granularity が指定されていない場合は port_size と同じ値にする
        if self.granularity is None:
            self.granularity = self.port_size
        # enditan が指定されていない場合、port_size == granularity の場合のみ許容
        if self.endian is None:
            if self.port_size != self.granularity:
                raise pydantic.ValidationError(
                    f"endian must be specified if port_size != granularity, but port_size={self.port_size}, granularity={self.granularity}"
                )
            else:
                # どちらでも挙動が変化しないので little に設定
                self.endian = "little"


class WishbonePort(wiring.Signature):
    """
    WishbonePort is a class that represents a Wishbone bus port with specified address and data widths.
    Attributes:
        addr_width (int): The width of the address bus.
        data_width (int): The width of the data bus.
        sel_width (int): The width of the byte select bus.
        tga_width (Optional[int]): The width of the address tag bus.
        tgd_i_width (Optional[int]): The width of the data tag input bus.
        tgd_o_width (Optional[int]): The width of the data tag output bus.
        tgc_width (Optional[int]): The width of the cycle tag bus.
    Methods:
        __init__(addr_width: int, data_width: int, tga_width: Optional[int] = None, tgd_i_width: Optional[int] = None, tgd_o_width: Optional[int] = None, tgc_width: Optional[int] = None): Initializes the WishbonePort with the given address and data widths and optional tag widths.
    """

    def __init__(
        self,
        addr_width: int,
        data_width: int,
        tga_width: Optional[int] = None,
        tgd_i_width: Optional[int] = None,
        tgd_o_width: Optional[int] = None,
        tgc_width: Optional[int] = None,
    ):
        self.addr_width = addr_width
        self.data_width = data_width
        self.sel_width = addr_width // 8  # byte sel
        self.tga_width = tga_width
        self.tgd_i_width = tgd_i_width
        self.tgd_o_width = tgd_o_width
        self.tgc_width = tgc_width

        # Required
        members = {
            # clk_i は省略
            # data input array
            "dat_i": In(self.data_width),
            # data output array
            "dat_o": Out(self.data_width),
            # wishbone interface reset
            "rst_i": In(1),
            # address output array
            "adr_o": Out(self.addr_width),
            # write enable/read enable output
            "we_o": Out(1),
            # byte enable output array
            "sel_o": Out(self.sel_width),
            # valid data transfer output
            "stb_o": Out(1),
            # bus cycle acknowledge input
            "ack_i": In(1),
            # bus cycle in progress output
            "cyc_o": Out(1),
            # bus cycle uninterruptible input
            "lock_o": Out(1),
            # error input
            "err_i": In(1),
            # not ready input
            "rty_i": Out(1),
        }

        # Optional
        if self.tga_width is not None:
            # address tag output
            members["tga_o"] = Out(self.tga_width)
        if self.tgd_i_width is not None:
            # data tag input
            members["tgd_i"] = In(self.tgd_i_width)
        if self.tgd_o_width is not None:
            # data tag output
            members["tgd_o"] = Out(self.tgd_o_width)
        if self.tgc_width is not None:
            # cycle tag output
            members["tgc_o"] = Out(self.tgc_width)

        super().__init__(members)

    def __eq__(self, other):
        return self.members == other.members


class Core(wiring.Component):
    """
    Top Component
    """

    def __init__(self):
        super().__init__({})

    def elaborate(self, platform):
        m = Module()
        return m
