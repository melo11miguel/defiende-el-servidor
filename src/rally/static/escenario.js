// Escenario del circuito de Mónaco: cielo, mar, ciudad, montañas, público, túnel.
// Todo esto es decoración: no cambia la física. Se ubica FUERA del muro del
// simulador, así lo que se ve nunca contradice lo que calcula Python.

import * as THREE from "three";
import { Sky } from "three/addons/objects/Sky.js";
import { Water } from "three/addons/objects/Water.js";

const rnd = (() => { let s = 12345; return () => ((s = (s * 16807) % 2147483647) / 2147483647); })();

// Distancia aproximada de un punto a la línea central (cubetas de 20 m)
function crearDistancia(centro) {
  const C = 20, cubetas = new Map();
  for (const [s, x, y] of centro) {
    const k = `${Math.floor(x / C)},${Math.floor(y / C)}`;
    if (!cubetas.has(k)) cubetas.set(k, []);
    cubetas.get(k).push([x, y, s]);
  }
  return (x, y) => {
    const cx = Math.floor(x / C), cy = Math.floor(y / C);
    let mejor = 1e9, sMejor = 0;
    for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) {
      for (const [px, py, s] of cubetas.get(`${cx + i},${cy + j}`) || []) {
        const d = (px - x) ** 2 + (py - y) ** 2;
        if (d < mejor) { mejor = d; sMejor = s; }
      }
    }
    return [Math.sqrt(mejor), sMejor];
  };
}

function texturaVentanas() {
  const c = document.createElement("canvas");
  c.width = 64; c.height = 128;
  const g = c.getContext("2d");
  g.fillStyle = "#fff"; g.fillRect(0, 0, 64, 128);
  for (let y = 6; y < 124; y += 14) for (let x = 5; x < 60; x += 13) {
    g.fillStyle = rnd() < 0.18 ? "#5b6b80" : "#3b4656";
    g.fillRect(x, y, 8, 9);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

function texturaBandera(colores) {
  const c = document.createElement("canvas");
  c.width = 48; c.height = 32;
  const g = c.getContext("2d");
  colores.forEach((col, i) => { g.fillStyle = col; g.fillRect(0, (i * 32) / colores.length, 48, 32 / colores.length + 1); });
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function texturaBanner(texto) {
  const c = document.createElement("canvas");
  c.width = 1024; c.height = 96;
  const g = c.getContext("2d");
  const grad = g.createLinearGradient(0, 0, 1024, 0);
  grad.addColorStop(0, "#0b1220"); grad.addColorStop(1, "#1e293b");
  g.fillStyle = grad; g.fillRect(0, 0, 1024, 96);
  g.font = "italic 900 58px Inter, Arial";
  g.textBaseline = "middle";
  const og = g.createLinearGradient(0, 20, 0, 80);
  og.addColorStop(0, "#fde047"); og.addColorStop(1, "#f97316");
  g.fillStyle = og;
  g.fillText(texto, 28, 50);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export function construirEscenario({ scene, renderer, pista, P, pared, cinta }) {
  const [MX, MY] = pista.mapa;
  const dist = crearDistancia(pista.centro);
  // ¿El punto está dentro del circuito? (prueba del rayo sobre el polígono de la línea central)
  const poli = pista.centro.filter((_, i) => i % 4 === 0).map(([, x, y]) => [x, y]);
  const dentro = (x, y) => {
    let c = false;
    for (let i = 0, j = poli.length - 1; i < poli.length; j = i++) {
      const [xi, yi] = poli[i], [xj, yj] = poli[j];
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
    }
    return c;
  };
  const muro = pista.ancho / 2 + pista.escape;
  const ys = pista.centro.map((c) => c[2]);
  const ORILLA = Math.min(...ys) - muro - 6; // el mar empieza al sur de la recta de meta

  // ---------------------------------------------------------------- cielo y sol
  const sky = new Sky();
  sky.scale.setScalar(2500);
  scene.add(sky);
  const u = sky.material.uniforms;
  u.turbidity.value = 6; u.rayleigh.value = 1.6; u.mieCoefficient.value = 0.006; u.mieDirectionalG.value = 0.86;
  const sol = new THREE.Vector3();
  const pmrem = new THREE.PMREMGenerator(renderer);
  let envRT = null;
  function ponerSol(elev, azim) {
    sol.setFromSphericalCoords(1, THREE.MathUtils.degToRad(90 - elev), THREE.MathUtils.degToRad(azim));
    u.sunPosition.value.copy(sol);
    if (envRT) envRT.dispose();
    const tmp = new THREE.Scene();
    tmp.add(sky.clone());
    envRT = pmrem.fromScene(tmp);
    scene.environment = envRT.texture;
  }

  // ---------------------------------------------------------------- mar
  const agua = new Water(new THREE.PlaneGeometry(3000, 3000), {
    textureWidth: 512, textureHeight: 512,
    waterNormals: new THREE.TextureLoader().load(
      // El paquete npm de three no incluye examples/textures (daba 404): se toma del repo en GitHub
      "https://cdn.jsdelivr.net/gh/mrdoob/three.js@r170/examples/textures/waternormals.jpg",
      (t) => { t.wrapS = t.wrapT = THREE.RepeatWrapping; }),
    sunDirection: new THREE.Vector3(), sunColor: 0xffe2b0, waterColor: 0x0b3a5c, distortionScale: 2.4,
    fog: true,
  });
  agua.rotation.x = -Math.PI / 2;
  agua.position.set(0, -0.6, -ORILLA + 1500);  // z = -y: el mar ocupa todo y < ORILLA
  scene.add(agua);

  // Malecón de piedra
  const malecon = new THREE.Mesh(new THREE.BoxGeometry(3000, 1.2, 4),
    new THREE.MeshStandardMaterial({ color: 0xcbbfa8, roughness: 0.9 }));
  malecon.position.copy(P(0, ORILLA - 2, -0.1));
  malecon.receiveShadow = true;
  scene.add(malecon);

  // Suelo de tierra firme (todo lo que está al norte de la orilla)
  const suelo = new THREE.Mesh(new THREE.PlaneGeometry(3000, 1500),
    new THREE.MeshStandardMaterial({ color: 0x9c9285, roughness: 1 }));
  suelo.rotation.x = -Math.PI / 2;
  suelo.position.set(0, -0.05, -(ORILLA + 750));
  suelo.receiveShadow = true;
  scene.add(suelo);

  // ---------------------------------------------------------------- yates
  const casco = new THREE.BoxGeometry(14, 2.2, 4.2);
  const cabina = new THREE.BoxGeometry(7, 2, 3.4);
  const NY = 34;
  const iCasco = new THREE.InstancedMesh(casco, new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.35, metalness: 0.1 }), NY);
  const iCab = new THREE.InstancedMesh(cabina, new THREE.MeshStandardMaterial({ color: 0x1f2937, roughness: 0.2, metalness: 0.5 }), NY);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Vector3();
  for (let i = 0; i < NY; i++) {
    const x = -MX + rnd() * 2 * MX, y = ORILLA - 14 - rnd() * 90, esc = 0.7 + rnd() * 0.9;
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), rnd() * Math.PI);
    e.set(esc, esc, esc);
    m.compose(P(x, y, 0.4 * esc), q, e); iCasco.setMatrixAt(i, m);
    m.compose(P(x, y, 2.3 * esc), q, e); iCab.setMatrixAt(i, m);
  }
  iCasco.castShadow = iCab.castShadow = true;
  scene.add(iCasco, iCab);

  // ---------------------------------------------------------------- ciudad
  const paleta = [0xf1e3c8, 0xe8c9a0, 0xd9a47a, 0xf3d7b5, 0xe6dccb, 0xc98f6b, 0xf5efe3, 0xd6b38a];
  const edificios = [];
  const paso = 13;
  const parque = [];  // dentro del circuito: jardines con árboles (como los del Casino)
  for (let x = -MX - 70; x <= MX + 70; x += paso) {
    for (let y = ORILLA + 10; y <= MY + 120; y += paso) {
      const jx = x + (rnd() - 0.5) * 3, jy = y + (rnd() - 0.5) * 3;
      const [d] = dist(jx, jy);
      if (d < muro + 7) continue;
      if (dentro(jx, jy)) {
        if (d > muro + 12 && rnd() < 0.08) edificios.push([jx, jy, 8 + rnd() * 4, 8 + rnd() * 4, 6 + rnd() * 7]);
        else parque.push([jx, jy]);
        continue;
      }
      if (d < muro + 14 || rnd() < 0.15) continue; // calles y plazas junto a la pista
      const lejos = Math.min(1, Math.max(0, d - 20) / 200);
      const alto = 5 + rnd() * 9 + lejos * rnd() * 30;
      edificios.push([jx, jy, 7 + rnd() * 4, 7 + rnd() * 4, alto]);
    }
  }
  // Césped del parque interior
  const formaParque = new THREE.Shape(pista.centro.filter((_, i) => i % 6 === 0).map(([, x, y]) => new THREE.Vector2(x, y)));
  const cesped = new THREE.Mesh(new THREE.ShapeGeometry(formaParque), new THREE.MeshStandardMaterial({ color: 0x5f8f3e, roughness: 1 }));
  cesped.rotation.x = -Math.PI / 2;
  cesped.position.y = -0.02;
  cesped.receiveShadow = true;
  scene.add(cesped);
  const matEdif = new THREE.MeshStandardMaterial({ map: texturaVentanas(), roughness: 0.75 });
  const iEdif = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), matEdif, edificios.length);
  const color = new THREE.Color();
  edificios.forEach(([x, y, lx, ly, h], i) => {
    m.compose(P(x, y, h / 2), new THREE.Quaternion(), new THREE.Vector3(lx, h, ly));
    iEdif.setMatrixAt(i, m);
    iEdif.setColorAt(i, color.setHex(paleta[Math.floor(rnd() * paleta.length)]));
  });
  iEdif.castShadow = iEdif.receiveShadow = true;
  scene.add(iEdif);
  // Techos de teja en algunos edificios
  const techos = edificios.filter(() => rnd() < 0.4);
  const iTecho = new THREE.InstancedMesh(new THREE.ConeGeometry(0.75, 1, 4), new THREE.MeshStandardMaterial({ color: 0xb4532a, roughness: 0.8, flatShading: true }), techos.length);
  techos.forEach(([x, y, lx, ly, h], i) => {
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.PI / 4);
    m.compose(P(x, y, h + 1.2), q, new THREE.Vector3(lx, 2.4, ly));
    iTecho.setMatrixAt(i, m);
  });
  scene.add(iTecho);

  // ---------------------------------------------------------------- montañas con bosque
  const montes = new THREE.Group();
  const matMonte = new THREE.MeshStandardMaterial({ color: 0x3f5a35, roughness: 1, flatShading: true });
  for (let i = 0; i < 26; i++) {
    const ang = Math.PI * (0.05 + 0.9 * (i / 25)) + (rnd() - 0.5) * 0.1;
    const r = 520 + rnd() * 260, alto = 90 + rnd() * 170;
    const monte = new THREE.Mesh(new THREE.ConeGeometry(160 + rnd() * 140, alto, 7), matMonte);
    monte.position.copy(P(Math.cos(ang) * r * 1.3, Math.sin(ang) * r + 60, alto / 2 - 5));
    monte.rotation.y = rnd() * 3;
    montes.add(monte);
  }
  scene.add(montes);
  // Árboles: bosque en las colinas + los del parque interior (2 por celda)
  const lugares = [];
  for (let i = 0; i < 700; i++) {
    const ang = Math.PI * (0.02 + 0.96 * rnd()), r = MY + 140 + rnd() * 330;
    lugares.push([Math.cos(ang) * r * 1.35, Math.sin(ang) * r + 30, 0.8 + rnd() * 1.1]);
  }
  for (const [x, y] of parque) for (let j = 0; j < 2; j++) {
    lugares.push([x + (rnd() - 0.5) * 9, y + (rnd() - 0.5) * 9, 0.45 + rnd() * 0.4]);
  }
  const NA = lugares.length;
  const iTronco = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.3, 0.4, 3, 5), new THREE.MeshStandardMaterial({ color: 0x4a3420 }), NA);
  const iCopa = new THREE.InstancedMesh(new THREE.ConeGeometry(2.6, 7, 6), new THREE.MeshStandardMaterial({ color: 0x2e5a2a, roughness: 0.9, flatShading: true }), NA);
  for (let i = 0; i < NA; i++) {
    const [x, y, esc] = lugares[i];
    e.set(esc, esc, esc);
    m.compose(P(x, y, 1.5 * esc), new THREE.Quaternion(), e); iTronco.setMatrixAt(i, m);
    m.compose(P(x, y, 6 * esc), new THREE.Quaternion(), e); iCopa.setMatrixAt(i, m);
    iCopa.setColorAt(i, color.setHSL(0.27 + rnd() * 0.07, 0.45, 0.2 + rnd() * 0.12));
  }
  iCopa.castShadow = true;
  scene.add(iTronco, iCopa);

  // ---------------------------------------------------------------- público y banderas
  const personas = [], banderas = [];
  const tramos = [[0, 140], [150, 215], [380, 440], [520, 600], [880, 960], [1000, pista.largo]];
  const enTramo = (s) => tramos.some(([a, b]) => s >= a && s <= b);
  for (let k = 0; k < pista.centro.length; k += 2) {
    const [s, x, y, h] = pista.centro[k];
    if (!enTramo(s)) continue;
    for (const lado of [1, -1]) {
      for (let fila = 0; fila < 3; fila++) {
        const off = lado * (muro + 1.4 + fila * 0.9);
        const px = x - Math.sin(h) * off + (rnd() - 0.5) * 0.5, py = y + Math.cos(h) * off;
        if (py < ORILLA + 1) continue;
        const [d, sd] = dist(px, py);
        if (Math.abs(sd - s) > 30 && Math.abs(sd - s) < pista.largo - 30) continue; // está junto a otro tramo
        if (d < muro + 1) continue;
        if (rnd() < 0.25) continue;
        personas.push([px, py, fila * 0.35, h]);
        if (fila === 2 && rnd() < 0.06) banderas.push([px, py, h]);
      }
    }
  }
  const ropa = [0xe11d48, 0x2563eb, 0xfacc15, 0xf8fafc, 0x16a34a, 0xf97316, 0x111827, 0x7c3aed];
  const iCuerpo = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.15, 0.18, 0.85, 6), new THREE.MeshStandardMaterial({ roughness: 0.8 }), personas.length);
  const iCabeza = new THREE.InstancedMesh(new THREE.SphereGeometry(0.12, 8, 6), new THREE.MeshStandardMaterial({ color: 0xd9a77e, roughness: 0.7 }), personas.length);
  personas.forEach(([x, y, z], i) => {
    m.compose(P(x, y, z + 0.43), new THREE.Quaternion(), new THREE.Vector3(1, 1, 1)); iCuerpo.setMatrixAt(i, m);
    m.compose(P(x, y, z + 0.98), new THREE.Quaternion(), new THREE.Vector3(1, 1, 1)); iCabeza.setMatrixAt(i, m);
    iCuerpo.setColorAt(i, color.setHex(ropa[Math.floor(rnd() * ropa.length)]));
  });
  scene.add(iCuerpo, iCabeza);
  // Gradas detrás del público
  const matGrada = new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.8 });
  for (let k = 0; k < personas.length; k += 9) {
    const [x, y, z] = personas[k];
    const g = new THREE.Mesh(new THREE.BoxGeometry(1.3, z + 0.05, 1.3), matGrada);
    g.position.copy(P(x, y, (z + 0.05) / 2));
    scene.add(g);
  }
  const flagsMat = [texturaBandera(["#e11d48", "#f8fafc"]), texturaBandera(["#f8fafc", "#2563eb", "#e11d48"]),
    texturaBandera(["#16a34a", "#f8fafc", "#e11d48"]), texturaBandera(["#111827", "#facc15", "#e11d48"])]
    .map((t) => new THREE.MeshStandardMaterial({ map: t, side: THREE.DoubleSide, roughness: 0.8 }));
  const grupoBanderas = new THREE.Group();
  const matPalo = new THREE.MeshStandardMaterial({ color: 0x9ca3af });
  banderas.forEach(([x, y, h], i) => {
    const g = new THREE.Group();
    g.position.copy(P(x, y, 0));
    g.rotation.y = h;
    const palo = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 3.4, 4), matPalo);
    palo.position.y = 1.7 + 0.7;
    const tela = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 0.8, 6, 1), flagsMat[i % flagsMat.length]);
    tela.position.set(0.6, 3.6, 0);
    g.add(palo, tela);
    g.userData.tela = tela;
    g.userData.fase = rnd() * 6;
    grupoBanderas.add(g);
  });
  scene.add(grupoBanderas);

  // ---------------------------------------------------------------- túnel
  const tunel = pista.curvas.find((c) => c.nombre === "Túnel");
  if (tunel) {
    const kt = 1 / tunel.radio;
    const idx = pista.centro.map((c, i) => [i, c]).filter(([, c]) => Math.abs(Math.abs(c[4]) - kt) < 1e-4).map(([i]) => i);
    const s0 = pista.centro[idx[0]][0] + 8, s1 = pista.centro[idx[idx.length - 1]][0] - 8;
    const solo = (f) => (s) => (s >= s0 && s <= s1 ? f(s) : null);
    const grupoT = new THREE.Group();
    const matT = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.8, side: THREE.DoubleSide });
    for (const off of [-muro - 0.6, muro + 0.6]) grupoT.add(new THREE.Mesh(paredTramo(pista, P, off, 0, 6.5, s0, s1, 0xd6d3d1), matT));
    grupoT.add(new THREE.Mesh(techoTramo(pista, P, -muro - 0.6, muro + 0.6, 6.5, s0, s1, 0x9ca3af), matT));
    const luces = new THREE.Mesh(techoTramo(pista, P, -0.4, 0.4, 6.45, s0, s1, 0xfff1c4),
      new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide, toneMapped: false }));
    grupoT.add(luces);
    grupoT.children.forEach((c) => { c.castShadow = true; c.receiveShadow = true; });
    scene.add(grupoT);
    void solo;
  }

  // ---------------------------------------------------------------- banners de patrocinio
  const banner = new THREE.MeshStandardMaterial({ map: texturaBanner("AUTONOMOUS RALLY · MONACO · MLOps EDITION"), roughness: 0.5, side: THREE.DoubleSide });
  for (let k = 40; k < pista.centro.length; k += 260) {
    const [, x, y, h] = pista.centro[k];
    for (const lado of [1, -1]) {
      const off = lado * (muro + 0.4);
      const px = x - Math.sin(h) * off, py = y + Math.cos(h) * off;
      const b = new THREE.Mesh(new THREE.PlaneGeometry(16, 1.5), banner);
      b.position.copy(P(px, py, 2.4));
      b.rotation.y = h;
      scene.add(b);
    }
  }

  // ---------------------------------------------------------------- clima
  const luzSol = scene.getObjectByName("sol");
  function aplicarClima(mojado) {
    if (mojado) {
      u.turbidity.value = 18; u.rayleigh.value = 0.6; u.mieCoefficient.value = 0.03;
      ponerSol(14, 15);
      scene.fog = new THREE.FogExp2(0x5b6676, 0.0042);
      renderer.toneMappingExposure = 0.55;
    } else {
      u.turbidity.value = 6; u.rayleigh.value = 1.6; u.mieCoefficient.value = 0.006;
      ponerSol(6, 15);  // atardecer dorado, sol bajo sobre el mar (al sur)
      scene.fog = new THREE.FogExp2(0xe8c49a, 0.0011);
      renderer.toneMappingExposure = 0.78;
    }
    if (luzSol) {
      luzSol.color.set(mojado ? 0xb8c4d6 : 0xffc488);
      luzSol.intensity = mojado ? 0.9 : 3.2;
      luzSol.position.copy(sol).multiplyScalar(260);
    }
    agua.material.uniforms.sunDirection.value.copy(sol).normalize();
    agua.material.uniforms.waterColor.value.set(mojado ? 0x1c2a36 : 0x0b3a5c);
    scene.background = null;
  }

  function actualizar(dt, t) {
    agua.material.uniforms.time.value += dt * 0.6;
    for (const g of grupoBanderas.children) g.userData.tela.rotation.y = Math.sin(t * 3 + g.userData.fase) * 0.35;
  }

  return { aplicarClima, actualizar };
}

// Pared y techo solo en un tramo de la pista (para el túnel)
function paredTramo(pista, P, off, h0, h1, s0, s1, hex) {
  const c = pista.centro.filter((p) => p[0] >= s0 && p[0] <= s1), pos = [], col = [];
  const k = new THREE.Color(hex);
  for (let i = 0; i < c.length - 1; i++) {
    const [, x, y, h] = c[i], [, x2, y2, h2] = c[i + 1];
    const a = P(x - Math.sin(h) * off, y + Math.cos(h) * off), b = P(x2 - Math.sin(h2) * off, y2 + Math.cos(h2) * off);
    for (const [p, hh] of [[a, h0], [b, h0], [a, h1], [a, h1], [b, h0], [b, h1]]) { pos.push(p.x, hh, p.z); col.push(k.r, k.g, k.b); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  g.computeVertexNormals();
  return g;
}

function techoTramo(pista, P, offA, offB, alto, s0, s1, hex) {
  const c = pista.centro.filter((p) => p[0] >= s0 && p[0] <= s1), pos = [], col = [];
  const k = new THREE.Color(hex);
  for (let i = 0; i < c.length - 1; i++) {
    const [, x, y, h] = c[i], [, x2, y2, h2] = c[i + 1];
    const pt = (xx, yy, hh, off) => P(xx - Math.sin(hh) * off, yy + Math.cos(hh) * off, alto);
    const a1 = pt(x, y, h, offA), b1 = pt(x, y, h, offB), a2 = pt(x2, y2, h2, offA), b2 = pt(x2, y2, h2, offB);
    for (const p of [a1, a2, b1, b1, a2, b2]) { pos.push(p.x, p.y, p.z); col.push(k.r, k.g, k.b); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  g.computeVertexNormals();
  return g;
}
