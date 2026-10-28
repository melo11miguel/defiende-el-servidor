// Carro de rally (silueta extruida, decoración, alerón) y humo de llantas.
// Las medidas son las del simulador: largo 4.0 m, ancho 1.8 m, entre ejes 2.5 m.

import * as THREE from "three";

function texturaDecoracion() {
  const c = document.createElement("canvas");
  c.width = 1024; c.height = 256;
  const g = c.getContext("2d");
  const fondo = g.createLinearGradient(0, 0, 1024, 0);
  fondo.addColorStop(0, "#1e3a8a"); fondo.addColorStop(0.55, "#1d4ed8"); fondo.addColorStop(1, "#0f172a");
  g.fillStyle = fondo; g.fillRect(0, 0, 1024, 256);
  // Franja dorada diagonal
  g.fillStyle = "#d4a017";
  g.beginPath(); g.moveTo(0, 160); g.lineTo(1024, 90); g.lineTo(1024, 140); g.lineTo(0, 215); g.closePath(); g.fill();
  g.fillStyle = "#facc15";
  g.beginPath(); g.moveTo(0, 222); g.lineTo(1024, 148); g.lineTo(1024, 158); g.lineTo(0, 232); g.closePath(); g.fill();
  // Número y nombre
  g.fillStyle = "#f8fafc"; g.beginPath(); g.roundRect(430, 40, 150, 110, 14); g.fill();
  g.fillStyle = "#0f172a"; g.font = "900 92px Inter, Arial"; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText("24", 505, 100);
  g.font = "italic 900 46px Inter, Arial"; g.textAlign = "left";
  g.fillStyle = "#fde047"; g.fillText("AUTONOMOUS", 620, 70);
  g.fillStyle = "#f8fafc"; g.fillText("RALLY", 620, 118);
  g.font = "700 30px Inter, Arial"; g.fillStyle = "#cbd5e1"; g.fillText("MLOps · PPO", 80, 70);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

export function crearCarro({ largo: L, ancho: W, ejes }) {
  const grupo = new THREE.Group();

  // Silueta lateral (x a lo largo, y altura) extruida a lo ancho
  const s = new THREE.Shape();
  const perfil = [[-2.02, 0.32], [-2.04, 0.78], [-1.7, 0.92], [-1.25, 0.96], [-0.85, 1.36], [0.2, 1.4],
    [0.9, 1.0], [1.65, 0.86], [2.0, 0.66], [2.04, 0.36], [1.75, 0.26], [-1.8, 0.26]];
  s.moveTo(perfil[0][0] * L / 4, perfil[0][1]);
  for (const [x, y] of perfil.slice(1)) s.lineTo(x * L / 4, y);
  s.closePath();
  const geo = new THREE.ExtrudeGeometry(s, { depth: W - 0.16, bevelEnabled: true, bevelThickness: 0.08, bevelSize: 0.08, bevelSegments: 3 });
  geo.translate(0, 0, -(W - 0.16) / 2);
  const pintura = new THREE.MeshPhysicalMaterial({
    map: texturaDecoracion(), metalness: 0.55, roughness: 0.28, clearcoat: 1, clearcoatRoughness: 0.06,
  });
  // UV laterales: proyección del perfil para que la decoración se vea en los costados
  // (en el costado derecho se invierte u para que el texto no salga en espejo)
  const pos = geo.attributes.position, uv = geo.attributes.uv, nor = geo.attributes.normal;
  for (let i = 0; i < pos.count; i++) {
    const u0 = (pos.getX(i) + L / 2) / L;
    uv.setXY(i, nor.getZ(i) < -0.5 ? 1 - u0 : u0, (pos.getY(i) - 0.2) / 1.3);
  }
  const cuerpo = new THREE.Mesh(geo, pintura);
  cuerpo.castShadow = true;
  grupo.add(cuerpo);

  // Vidrios (un poco más afuera que la carrocería)
  const v = new THREE.Shape();
  const pv = [[-1.18, 0.98], [-0.82, 1.32], [0.18, 1.35], [0.84, 1.02]];
  v.moveTo(pv[0][0] * L / 4, pv[0][1]);
  for (const [x, y] of pv.slice(1)) v.lineTo(x * L / 4, y);
  v.closePath();
  const vidrio = new THREE.MeshPhysicalMaterial({ color: 0x0b1220, metalness: 0.4, roughness: 0.04, clearcoat: 1 });
  const gv = new THREE.ExtrudeGeometry(v, { depth: W - 0.02, bevelEnabled: false });
  gv.translate(0, 0.005, -(W - 0.02) / 2);
  grupo.add(new THREE.Mesh(gv, vidrio));

  const negro = new THREE.MeshStandardMaterial({ color: 0x0b0f17, roughness: 0.5, metalness: 0.3 });
  const dorado = new THREE.MeshStandardMaterial({ color: 0xc9a227, metalness: 0.9, roughness: 0.25 });
  const add = (g, mat, x, y, z, ry = 0) => { const m = new THREE.Mesh(g, mat); m.position.set(x, y, z); m.rotation.y = ry; m.castShadow = true; grupo.add(m); return m; };
  // Alerón trasero con soportes
  add(new THREE.BoxGeometry(0.42, 0.06, W + 0.1), negro, -L * 0.47, 1.42, 0);
  for (const z of [0.55, -0.55]) add(new THREE.BoxGeometry(0.12, 0.36, 0.06), negro, -L * 0.45, 1.22, z);
  for (const z of [W / 2 + 0.05, -W / 2 - 0.05]) add(new THREE.BoxGeometry(0.46, 0.3, 0.03), dorado, -L * 0.47, 1.36, z);
  // Toma de aire en el techo, espejos y parachoques
  add(new THREE.BoxGeometry(0.5, 0.12, 0.35), negro, -0.05, 1.46, 0);
  for (const z of [W / 2 + 0.1, -W / 2 - 0.1]) add(new THREE.BoxGeometry(0.16, 0.1, 0.12), negro, L * 0.2, 1.08, z);
  add(new THREE.BoxGeometry(0.18, 0.18, W + 0.08), negro, L / 2 + 0.02, 0.36, 0);
  add(new THREE.BoxGeometry(0.16, 0.2, W + 0.04), negro, -L / 2 - 0.02, 0.38, 0);
  // Guardafangos ensanchados
  for (const x of [ejes / 2, -ejes / 2]) for (const z of [W / 2, -W / 2]) {
    const arco = add(new THREE.CylinderGeometry(0.48, 0.48, 0.18, 16, 1, false, 0, Math.PI), negro, x, 0.42, z);
    arco.rotation.set(Math.PI / 2, 0, -Math.PI / 2);
  }

  // Luces
  const faroMat = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff3c4, emissiveIntensity: 3 });
  for (const z of [0.58, -0.58]) add(new THREE.BoxGeometry(0.06, 0.12, 0.34), faroMat, L / 2 + 0.03, 0.66, z);
  const luzFreno = new THREE.MeshStandardMaterial({ color: 0x7f1d1d, emissive: 0xff1e1e, emissiveIntensity: 0.6 });
  for (const z of [0.62, -0.62]) add(new THREE.BoxGeometry(0.06, 0.1, 0.4), luzFreno, -L / 2 - 0.04, 0.74, z);

  // Ruedas: pivote (dirección) → giro (rodar) → llanta + rin dorado
  const ruedas = [];
  const geoLlanta = new THREE.CylinderGeometry(0.36, 0.36, 0.3, 28);
  const llanta = new THREE.MeshStandardMaterial({ color: 0x0a0a0a, roughness: 0.92 });
  for (const [x, z, delantera] of [[ejes / 2, W / 2, true], [ejes / 2, -W / 2, true], [-ejes / 2, W / 2, false], [-ejes / 2, -W / 2, false]]) {
    const pivote = new THREE.Group();
    pivote.position.set(x, 0.36, z);
    const giro = new THREE.Group();
    const l = new THREE.Mesh(geoLlanta, llanta);
    l.rotation.x = Math.PI / 2;
    l.castShadow = true;
    const rin = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.32, 10), dorado);
    rin.rotation.x = Math.PI / 2;
    for (let k = 0; k < 5; k++) {
      const rayo = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.36, 0.33), dorado);
      rayo.rotation.set(Math.PI / 2, (k * Math.PI * 2) / 5, 0);
      giro.add(rayo);
    }
    giro.add(l, rin);
    pivote.add(giro);
    grupo.add(pivote);
    ruedas.push({ pivote, giro, delantera });
  }

  const faro = new THREE.SpotLight(0xfff3c4, 0, 60, 0.45, 0.6, 1.2);
  faro.position.set(L / 2, 0.8, 0);
  faro.target.position.set(L / 2 + 10, 0, 0);
  grupo.add(faro, faro.target);
  return { grupo, ruedas, luzFreno, faro };
}

// ------------------------------------------------------------------ humo
function texturaHumo() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d");
  const r = g.createRadialGradient(32, 32, 2, 32, 32, 32);
  r.addColorStop(0, "rgba(255,255,255,0.9)"); r.addColorStop(0.5, "rgba(235,235,235,0.35)"); r.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = r; g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

export function crearHumo(scene, N = 420) {
  const pos = new Float32Array(N * 3), tam = new Float32Array(N), alfa = new Float32Array(N);
  const vel = new Float32Array(N * 3), vida = new Float32Array(N);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geo.setAttribute("tam", new THREE.BufferAttribute(tam, 1));
  geo.setAttribute("alfa", new THREE.BufferAttribute(alfa, 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { mapa: { value: texturaHumo() }, color: { value: new THREE.Color(0xe7e2dc) } },
    vertexShader: `attribute float tam; attribute float alfa; varying float vA;
      void main(){ vA = alfa; vec4 mv = modelViewMatrix * vec4(position,1.0);
      gl_PointSize = tam * 320.0 / -mv.z; gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform sampler2D mapa; uniform vec3 color; varying float vA;
      void main(){ vec4 t = texture2D(mapa, gl_PointCoord); gl_FragColor = vec4(color, t.a * vA); }`,
    transparent: true, depthWrite: false,
  });
  const puntos = new THREE.Points(geo, mat);
  puntos.frustumCulled = false;
  scene.add(puntos);
  let k = 0;

  function emitir(p, intensidad) {
    const n = Math.ceil(intensidad * 3);
    for (let j = 0; j < n; j++) {
      const i = k++ % N;
      pos[i * 3] = p.x + (Math.random() - 0.5) * 0.4; pos[i * 3 + 1] = 0.25; pos[i * 3 + 2] = p.z + (Math.random() - 0.5) * 0.4;
      vel[i * 3] = (Math.random() - 0.5) * 1.2; vel[i * 3 + 1] = 0.6 + Math.random() * 0.8; vel[i * 3 + 2] = (Math.random() - 0.5) * 1.2;
      vida[i] = 1; tam[i] = 0.6 + Math.random() * 0.4; alfa[i] = 0.35 * intensidad + 0.15;
    }
  }

  function actualizar(dt) {
    for (let i = 0; i < N; i++) {
      if (vida[i] <= 0) { alfa[i] = 0; continue; }
      vida[i] -= dt * 0.55;
      pos[i * 3] += vel[i * 3] * dt; pos[i * 3 + 1] += vel[i * 3 + 1] * dt; pos[i * 3 + 2] += vel[i * 3 + 2] * dt;
      tam[i] += dt * 2.6;
      alfa[i] = Math.max(0, alfa[i] - dt * 0.35);
    }
    geo.attributes.position.needsUpdate = geo.attributes.tam.needsUpdate = geo.attributes.alfa.needsUpdate = true;
  }
  return { emitir, actualizar, puntos };
}
