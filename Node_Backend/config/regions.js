//IMPORTANT
// Predefined areas shown in the dashboard dropdown.
// `id` must match the region_id you send to /api/analyze when pre processing,
// and the region_id FastAPI copies back in its response.
// `center`/`zoom` are just used for an initial nice map view before data loads.

export const REGIONS = [
  { id: "bengaluru_koramangala", name: "Koramangala", center: [12.9352, 77.6146], zoom: 14 },
  { id: "bengaluru_indiranagar", name: "Indiranagar (demo)", center: [12.9784, 77.6408], zoom: 14 },
  { id: "bengaluru_whitefield", name: "Whitefield", center: [12.9698, 77.7500], zoom: 13 },
  { id: "bengaluru_electronic_city", name: "Electronic City", center: [12.8452, 77.6602], zoom: 13 },
  { id: "bengaluru_hebbal", name: "Hebbal / ORR Junction", center: [13.0355, 77.5973], zoom: 14 },
  { id: "bengaluru_jayanagar", name: "Jayanagar / Banashankari", center: [12.9250, 77.5938], zoom: 14 },
];
