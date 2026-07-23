async function test() {
  const url1 = "https://2ff3-103-147-8-75.ngrok-free.app/v1/incidents";
  const url2 = "https://2ff3-103-147-8-75.ngrok-free.app/v1/incidents?crime_type=Begal&crime_type=Geng%20Motor";
  
  const headers = {
    "ngrok-skip-browser-warning": "true",
    "User-Agent": "curl/7.68.0"
  };

  const res1 = await fetch(url1, { headers });
  console.log("No query params:", res1.status, (await res1.text()).substring(0, 50));

  const res2 = await fetch(url2, { headers });
  console.log("With query params:", res2.status, (await res2.text()).substring(0, 50));
}

test();
