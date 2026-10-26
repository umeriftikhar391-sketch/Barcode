export type Product = {
  id: string;
  name: string;
  barcode: string;
  price: string;
  symbol: string;
  currency: string;
  quantity: number;
  source: string;
  reference: string;
};
export type Geometry = {
  backing: number;
  width: number;
  height: number;
  columns: number;
  gap_x: number;
  gap_y: number;
  left: number;
  right: number;
  top: number;
  offset_x: number;
  origin: number;
  safe: number;
  printable: number;
  dpi: number;
  density: number;
  speed: number;
};
export type Queue = { products: Product[]; geometry: Geometry };
export const currencies = [
  ["PKR", "Pakistani Rupee", "Rs."],
  ["PKR", "Pakistani Rupee", "₨"],
  ["USD", "US Dollar", "$"],
  ["EUR", "Euro", "€"],
  ["GBP", "British Pound", "£"],
  ["AED", "UAE Dirham", "د.إ"],
  ["SAR", "Saudi Riyal", "﷼"],
];
