export type Airport = {
  iata: string;
  name: string;
  city: string;
  latitude: number;
  longitude: number;
};

export const AIRPORTS: Airport[] = [
  { iata: "PEK", name: "北京首都国际机场", city: "北京", latitude: 40.0799, longitude: 116.6031 },
  { iata: "PKX", name: "北京大兴国际机场", city: "北京", latitude: 39.5098, longitude: 116.4105 },
  { iata: "PVG", name: "上海浦东国际机场", city: "上海", latitude: 31.1443, longitude: 121.8083 },
  { iata: "SHA", name: "上海虹桥国际机场", city: "上海", latitude: 31.1979, longitude: 121.3363 },
  { iata: "HGH", name: "杭州萧山国际机场", city: "杭州", latitude: 30.2295, longitude: 120.4344 },
  { iata: "WUX", name: "无锡硕放机场", city: "无锡", latitude: 31.4944, longitude: 120.429 },
  { iata: "NKG", name: "南京禄口国际机场", city: "南京", latitude: 31.742, longitude: 118.862 },
  { iata: "NGB", name: "宁波栎社国际机场", city: "宁波", latitude: 29.8267, longitude: 121.4619 },
  { iata: "HFE", name: "合肥新桥国际机场", city: "合肥", latitude: 31.9878, longitude: 116.9769 },
  { iata: "TAO", name: "青岛胶东国际机场", city: "青岛", latitude: 36.3617, longitude: 120.0883 },
  { iata: "TSN", name: "天津滨海国际机场", city: "天津", latitude: 39.1244, longitude: 117.3462 },
  { iata: "SZX", name: "深圳宝安国际机场", city: "深圳", latitude: 22.6393, longitude: 113.8107 },
  { iata: "CAN", name: "广州白云国际机场", city: "广州", latitude: 23.3924, longitude: 113.2988 },
  { iata: "CTU", name: "成都双流国际机场", city: "成都", latitude: 30.5785, longitude: 103.9471 },
  { iata: "TFU", name: "成都天府国际机场", city: "成都", latitude: 30.3125, longitude: 104.441 },
  { iata: "WUH", name: "武汉天河国际机场", city: "武汉", latitude: 30.7838, longitude: 114.2081 },
  { iata: "CSX", name: "长沙黄花国际机场", city: "长沙", latitude: 28.1892, longitude: 113.2200 },
  { iata: "XIY", name: "西安咸阳国际机场", city: "西安", latitude: 34.4471, longitude: 108.7516 },
  { iata: "XMN", name: "厦门高崎国际机场", city: "厦门", latitude: 24.544, longitude: 118.1277 },
  { iata: "FOC", name: "福州长乐国际机场", city: "福州", latitude: 25.9351, longitude: 119.6633 },
  { iata: "KMG", name: "昆明长水国际机场", city: "昆明", latitude: 25.1019, longitude: 102.9292 },
  { iata: "CKG", name: "重庆江北国际机场", city: "重庆", latitude: 29.7192, longitude: 106.6417 },
  { iata: "HAK", name: "海口美兰国际机场", city: "海口", latitude: 19.9349, longitude: 110.4589 },
  { iata: "SYX", name: "三亚凤凰国际机场", city: "三亚", latitude: 18.3029, longitude: 109.4123 },
];

const CITY_COORDINATES: Record<string, [number, number]> = {
  上海: [31.2304, 121.4737],
  苏州: [31.2989, 120.5853],
  无锡: [31.4912, 120.3119],
  嘉兴: [30.7467, 120.7555],
  杭州: [30.2741, 120.1551],
  北京: [39.9042, 116.4074],
  天津: [39.0842, 117.201],
  南京: [32.0603, 118.7969],
  宁波: [29.8683, 121.544],
  合肥: [31.8206, 117.2272],
  青岛: [36.0671, 120.3826],
  深圳: [22.5431, 114.0579],
  广州: [23.1291, 113.2644],
  成都: [30.5728, 104.0668],
  武汉: [30.5928, 114.3055],
  长沙: [28.2282, 112.9388],
  西安: [34.3416, 108.9398],
  厦门: [24.4798, 118.0894],
  福州: [26.0745, 119.2965],
  昆明: [25.0389, 102.7183],
  重庆: [29.563, 106.5516],
  海口: [20.044, 110.1999],
  三亚: [18.2528, 109.5119],
};

export function placeCoordinates(name: string): { latitude: number; longitude: number } | null {
  const matchedCity = Object.keys(CITY_COORDINATES).find((city) => name.includes(city));
  if (!matchedCity) return null;
  const [latitude, longitude] = CITY_COORDINATES[matchedCity];
  return { latitude, longitude };
}

export function airportDistanceKm(
  point: { latitude: number; longitude: number },
  airport: Airport,
): number {
  const radians = Math.PI / 180;
  const lat1 = point.latitude * radians;
  const lat2 = airport.latitude * radians;
  const deltaLat = (airport.latitude - point.latitude) * radians;
  const deltaLon = (airport.longitude - point.longitude) * radians;
  const a = Math.sin(deltaLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLon / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function nearestAirport(point: { latitude: number; longitude: number } | null): Airport | null {
  if (!point || !Number.isFinite(point.latitude) || !Number.isFinite(point.longitude)) return null;
  return AIRPORTS.reduce((nearest, airport) =>
    airportDistanceKm(point, airport) < airportDistanceKm(point, nearest) ? airport : nearest,
  );
}
