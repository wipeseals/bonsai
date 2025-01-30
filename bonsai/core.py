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
        support_lock_o (bool): Whether lock support is enabled.
        support_tga_o (Optional[WishboneTag]): The tag support for the address bus.
        support_tgd_i (Optional[WishboneTag]): The tag support for the data input bus.
        support_tgd_o (Optional[WishboneTag]): The tag support for the data output bus.
        support_tgc_o (Optional[WishboneTag]): The tag support for the cycle bus.
        endian (Optional[Literal["little", "big"]]): The endianness of the Wishbone bus.
    """

    port_size: Literal[8, 16, 32, 64]
    granularity: Literal[8, 16, 32, 64]
    spec_rev: str = "B4"
    support_err_i: bool = False
    support_rty_i: bool = False
    support_lock_o: bool = False
    support_tga_o: Optional[WishboneTag] = None
    support_tgd_i: Optional[WishboneTag] = None
    support_tgd_o: Optional[WishboneTag] = None
    support_tgc_o: Optional[WishboneTag] = None
    endian: Optional[Literal["little", "big"]] = None

    @property
    def addr_width(self) -> int:
        return self.port_size

    @property
    def data_width(self) -> int:
        return self.granularity

    @property
    def sel_width(self) -> int:
        return self.granularity // 8

    def __post_init_post_parse__(self):
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
    WishbonePort is a class that represents a Wishbone bus port with a specified specification.
    Attributes:
        spec (WishboneSpec): The specification of the Wishbone bus.
    Methods:
        __init__(spec: WishboneSpec): Initializes the WishbonePort with the given specification.
    """

    def __init__(
        self,
        spec: WishboneSpec,
    ):
        self.spec = spec

        # Required
        members = {
            # clk_i は省略
            # data input array
            "dat_i": In(self.spec.data_width),
            # data output array
            "dat_o": Out(self.spec.data_width),
            # wishbone interface reset
            "rst_i": In(1),
            # address output array
            "adr_o": Out(self.spec.addr_width),
            # write enable/read enable output
            "we_o": Out(1),
            # byte enable output array
            "sel_o": Out(self.spec.sel_width),
            # valid data transfer output
            "stb_o": Out(1),
            # bus cycle acknowledge input
            "ack_i": In(1),
            # bus cycle in progress output
            "cyc_o": Out(1),
        }

        # feature support (optional)
        if self.spec.support_err_i:
            # error input
            members["err_i"] = In(1)
        if self.spec.support_rty_i:
            # not ready input
            members["rty_i"] = Out(1)
        if self.spec.support_lock_o:
            # bus cycle uninterruptible input
            members["lock_o"] = Out(1)
        # tag support (optional)
        if self.spec.support_tga_o is not None:
            # address tag output
            members["tga_o"] = Out(self.spec.support_tga_o.width)
        if self.spec.support_tgd_i is not None:
            # data tag input
            members["tgd_i"] = In(self.spec.support_tgd_i.width)
        if self.spec.support_tgd_o is not None:
            # data tag output
            members["tgd_o"] = Out(self.spec.support_tgd_o.width)
        if self.spec.support_tgc_o is not None:
            # cycle tag output
            members["tgc_o"] = Out(self.spec.support_tgc_o.width)

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
