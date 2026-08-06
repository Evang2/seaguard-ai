export interface RecentPosition {
  id: number;
  mmsi: string;
  vessel_name: string | null;
  vessel_type: number | null;
  timestamp: string;
  latitude: number;
  longitude: number;
  sog: number | null;
  cog: number | null;
  heading: number | null;
  navigation_status: number | null;
}

export interface RecentPositionsResponse {
  items: RecentPosition[];
  total: number;
}