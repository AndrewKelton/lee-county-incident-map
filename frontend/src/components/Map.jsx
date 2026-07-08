import React, { useEffect, useState } from "react";
import {
  MapContainer,
  TileLayer,
  useMap,
  Marker,
  Popup,
  GeoJSON,
  Polygon,
  CircleMarker,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import MarkerClusterGroup from "react-leaflet-cluster";
import "react-leaflet-cluster/dist/assets/MarkerCluster.css";
import "react-leaflet-cluster/dist/assets/MarkerCluster.Default.css";

const iconCache = {};
//create a custom hook to move the map when user click on the item
function MoveMap({ selectedLocation, countyCenter }) {
  const map = useMap();

  useEffect(() => {
    if (selectedLocation) {
      map.flyTo([selectedLocation[0], selectedLocation[1]], 18, {
        duration: 1.2,
      });
    }
  }, [selectedLocation]);
  return null;
}
function Map({ finalList, countyCenter, locationMove }) {
  const [leeCounty, setLeeCounty] = useState(null);
  useEffect(() => {
    fetch("/lee-county.json")
      .then((res) => res.json())
      .then(setLeeCounty);
  }, []);
  const LEECOUNTY_BOUNDARY = [
    [
      [26.78980006125687, -82.272362941444],
      [26.789845555613542, -82.26674734260132],
      [26.78506785591573, -82.24039974363203],
      [26.784682327821244, -82.23903842851749],
      [26.78466547444208, -82.2389791674873],
      [26.7820416567969, -82.22592358399687],
      [26.782041344440042, -82.2232956474719],
      [26.771383695762992, -82.20659552905133],
      [26.771385640979, -82.20647976655594],
      [26.771392588357518, -82.20606614853668],
      [26.771432134382756, -82.20371036771571],
      [26.771451667543054, -82.20254589924075],
      [26.771455409378866, -82.20232270862869],
      [26.770580132044987, -82.06111276257575],
      [26.769557491947527, -81.56583524283978],
      [26.422579371979108, -81.56212541999152],
      [26.42121661767304, -81.65945294404435],
      [26.317535087331482, -81.65801989377533],
      [26.316233491651623, -81.81902174232401],
      [26.330254811084547, -81.84588796417505],
      [26.329835733418385, -82.2449563152756],
      [26.419874753315746, -82.33457334444688],
      [26.6450848069833, -82.42798337825371],
      [26.736154829652275, -82.43157338143331],
      [26.788130900846568, -82.46253412522209],
      [26.78980006125687, -82.272362941444],
    ],
  ];
  // Get incident color
  // Color palette keyed by incident nature (first word, lowercase)
  const NATURE_COLORS = {
    disturbance: "#e74c3c",
    assault: "#c0392b",
    theft: "#e67e22",
    burglary: "#d35400",
    traffic: "#3498db",
    suspicious: "#9b59b6",
    medical: "#1abc9c",
    fire: "#e74c3c",
    welfare: "#27ae60",
    domestic: "#c0392b",
    default: "#7f8c8d",
  };

  function getIncidentColor(type) {
    const lowerType = type.toLowerCase();
    for (const keyword in NATURE_COLORS) {
      if (lowerType.includes(keyword)) {
        return NATURE_COLORS[keyword];
      }
    }
    return NATURE_COLORS["default"];
  }

  function createIncidentIcon(nature) {
    const color = getIncidentColor(nature);
    if (!iconCache[color]) {
      iconCache[color] = L.divIcon({
        className: "",
        html: `
          <div style="
        width: 18px;
        height: 18px;
        background: ${color};
        border: 2px solid white;
        border-radius: 50%;">
          
          </div>
        `,
        iconSize: [18, 18],
        iconAnchor: [9, 9],
      });
    }
    return iconCache[color];
  }
  return (
    <MapContainer
      center={countyCenter}
      zoom={10}
      scrollWheelZoom={true}
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        className="dark-map"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {/*create a custom hook to move the map when user click on the item */}
      <MoveMap selectedLocation={locationMove} />
      {leeCounty && (
        <GeoJSON data={leeCounty} style={{ color: "red", weight: 4 }} />
      )}
      {leeCounty && (
        <Polygon
          positions={[
            [
              [-90, -180],
              [-90, 180],
              [90, 180],
              [90, -180],
              [-90, -180],
            ],
            LEECOUNTY_BOUNDARY,
          ]}
          pathOptions={{
            fillColor: "black",
            fillOpacity: 0.4,
            stroke: false,
          }}
        />
      )}
      <MarkerClusterGroup>
        {finalList.map((incident, index) => (
          <Marker
            key={incident.id}
            position={[incident.lat, incident.lng]}
            icon={createIncidentIcon(incident.nature)}
          >
            <Popup>incident address {index}</Popup>
          </Marker>
        ))}
      </MarkerClusterGroup>
    </MapContainer>
  );
}

export default Map;
