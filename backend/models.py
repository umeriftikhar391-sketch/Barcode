from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Product(Strict):
    id: str = Field(default_factory=lambda: str(uuid4()), max_length=100)
    name: str = Field(min_length=1, max_length=300)
    barcode: str = Field(min_length=1, max_length=128)
    price: Decimal = Field(ge=0, max_digits=16, decimal_places=4)
    symbol: str = Field(min_length=1, max_length=12)
    currency: str = Field(default="", max_length=12)
    quantity: int = Field(strict=True, ge=1, le=10000)
    source: str = Field(default="manual", max_length=32)
    reference: str = Field(default="", max_length=200)

    @field_validator("name", "symbol")
    @classmethod
    def text(cls, v):
        if not v.strip() or any(ord(c) < 32 for c in v):
            raise ValueError("Text must be nonblank and have no control characters")
        return v

    @field_validator("barcode")
    @classmethod
    def code(cls, v):
        if any(not 32 <= ord(c) <= 126 for c in v):
            raise ValueError(
                "Code 128 supports printable ASCII here, not arbitrary Unicode"
            )
        return v


class Geometry(Strict):
    backing: float = Field(default=107, gt=0, le=112)
    width: float = Field(default=35, gt=0, le=108)
    height: float = Field(default=25, ge=10, le=100)
    columns: int = Field(default=3, ge=3, le=3)
    gap_x: float = Field(default=2, ge=0, le=20)
    gap_y: float = Field(default=2, ge=0, le=20)
    left: float = Field(default=2, ge=0, le=20)
    right: float = Field(default=2, ge=0, le=20)
    top: float = Field(default=0, ge=0, le=20)
    offset_x: float = Field(default=0, ge=-20, le=20)
    origin: float = Field(default=0, ge=0, le=20)
    safe: float = Field(default=1, ge=0.5, le=8)
    printable: float = Field(default=108, gt=0, le=108)
    dpi: int = Field(default=203, ge=203, le=203)
    density: int = Field(default=8, ge=0, le=15)
    speed: int = Field(default=2, ge=1, le=6)
    barcode_module: int = Field(default=2, ge=1, le=2, strict=True)

    def dots(self, mm):
        return int(
            (Decimal(str(mm)) * Decimal(self.dpi) / Decimal("25.4")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )

    def errors(self):
        e = []
        extent = (
            self.left
            + self.columns * self.width
            + (self.columns - 1) * self.gap_x
            + self.right
        )
        if extent > self.backing + 1e-6:
            e.append(
                f"Labels, gaps and margins total {extent:g} mm, exceeding {self.backing:g} mm backing."
            )
        if self.top + 2 * self.safe >= self.height:
            e.append("Top offset and safe margins leave no vertical content area.")
        if 2 * self.safe >= self.width:
            e.append("Safe margins leave no horizontal content area.")
        for c in range(self.columns):
            x = self.left + c * (self.width + self.gap_x) + self.offset_x
            if x < 0 or x + self.width > self.backing:
                e.append(f"Column {c + 1} falls outside backing.")
            a = x + self.safe - self.origin
            b = x + self.width - self.safe - self.origin
            if (
                a < 0
                or b > self.printable
                or self.dots(a) < 0
                or self.dots(b) > self.dots(self.printable)
            ):
                e.append(f"Column {c + 1} content falls outside printable region.")
        return e


class Queue(Strict):
    products: list[Product] = Field(default_factory=list, max_length=5000)
    geometry: Geometry = Field(default_factory=Geometry)

    @field_validator("products")
    @classmethod
    def limits(cls, v):
        if sum(p.quantity for p in v) > 10000:
            raise ValueError("Maximum 10,000 labels per job")
        if len({p.id for p in v}) != len(v):
            raise ValueError("Queue IDs must be unique")
        return v
