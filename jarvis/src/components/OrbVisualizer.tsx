import { useEffect, useRef } from "react";
import * as THREE from "three";

export type OrbState = "idle" | "listening" | "thinking" | "speaking";

// ── State targets ────────────────────────────────────────────────────────────
interface StateTarget {
  particleCount: number;
  radius:        number;
  connectionDist: number;
  pointSize:     number;
  rotationSpeed: number;
  coreScale:     number;
  colorParticle: THREE.Color;
  colorLine:     THREE.Color;
  colorCore:     THREE.Color;
}

// connectionDist reduced 20% vs original for fewer, more readable connections
const T: Record<OrbState, StateTarget> = {
  idle: {
    particleCount: 350, radius: 1.30, connectionDist: 0.42, pointSize: 3.75,
    rotationSpeed: 0.0003, coreScale: 1.0,
    colorParticle: new THREE.Color(0xa78bfa),
    colorLine:     new THREE.Color(0x6366f1),
    colorCore:     new THREE.Color(0x818cf8),
  },
  listening: {
    particleCount: 80,  radius: 0.85, connectionDist: 0.36, pointSize: 2.0,
    rotationSpeed: 0.0002, coreScale: 0.75,
    colorParticle: new THREE.Color(0x6366f1),
    colorLine:     new THREE.Color(0x4f46e5),
    colorCore:     new THREE.Color(0x6366f1),
  },
  thinking: {
    particleCount: 175, radius: 1.10, connectionDist: 0.46, pointSize: 3.0,
    rotationSpeed: 0.0042, coreScale: 1.4,
    colorParticle: new THREE.Color(0xc4b5fd),
    colorLine:     new THREE.Color(0x9333ea),
    colorCore:     new THREE.Color(0xa78bfa),
  },
  speaking: {
    particleCount: 220, radius: 1.15, connectionDist: 0.50, pointSize: 3.5,
    rotationSpeed: 0.0008, coreScale: 1.8,
    colorParticle: new THREE.Color(0xddd6fe),
    colorLine:     new THREE.Color(0xc4b5fd),
    colorCore:     new THREE.Color(0xffffff),
  },
};

// ── Constants ────────────────────────────────────────────────────────────────
const MAX_PARTICLES  = 400;
const MAX_LINE_VERTS = 12000; // 6000 segments × 2 vertices

// Pre-computed Fibonacci sphere directions — unit radius, y ∈ (-1, 1)
const BASE_DIRS = (() => {
  const out = new Float32Array(MAX_PARTICLES * 3);
  const phi = Math.PI * (Math.sqrt(5) - 1);
  for (let i = 0; i < MAX_PARTICLES; i++) {
    const y = 1 - (2 * i + 1) / MAX_PARTICLES;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const t = phi * i;
    out[i * 3]     = Math.cos(t) * r;
    out[i * 3 + 1] = y;
    out[i * 3 + 2] = Math.sin(t) * r;
  }
  return out;
})();

// Per-particle organic oscillation params (random at module load, stable per session)
const PARTICLE_FREQS  = Float32Array.from({ length: MAX_PARTICLES }, () => 0.3 + Math.random() * 0.5);  // 0.3–0.8 Hz
const PARTICLE_PHASES = Float32Array.from({ length: MAX_PARTICLES }, () => Math.random() * Math.PI * 2); // 0–2π
const PARTICLE_AMPS   = Float32Array.from({ length: MAX_PARTICLES }, () => 0.04 + Math.random() * 0.02); // 0.04–0.06

// ── Shaders ──────────────────────────────────────────────────────────────────
const PARTICLE_VERT = /* glsl */`
uniform float ptSize;
void main() {
  gl_PointSize = ptSize;
  gl_Position  = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const PARTICLE_FRAG = /* glsl */`
uniform vec3 ptColor;
void main() {
  float d = length(gl_PointCoord - 0.5);
  if (d > 0.5) discard;
  float alpha = 1.0 - smoothstep(0.25, 0.5, d);
  gl_FragColor = vec4(ptColor, alpha);
}`;

const LINE_VERT = /* glsl */`
attribute float aAlpha;
varying float   vAlpha;
void main() {
  vAlpha      = aAlpha;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const LINE_FRAG = /* glsl */`
uniform vec3  lineColor;
uniform float lineOpacity;
varying float vAlpha;
void main() {
  gl_FragColor = vec4(lineColor, vAlpha * lineOpacity);
}`;

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

// ── Component ────────────────────────────────────────────────────────────────
export function OrbVisualizer({
  state,
  audioLevel = 0,
}: {
  state: OrbState;
  audioLevel?: number;
}) {
  const containerRef  = useRef<HTMLDivElement>(null);
  const stateRef      = useRef(state);
  const audioLevelRef = useRef(audioLevel);

  stateRef.current      = state;
  audioLevelRef.current = audioLevel;

  useEffect(() => {
    const container = containerRef.current!;
    let W = container.clientWidth;
    let H = container.clientHeight;

    // ── Scene / Camera ─────────────────────────────────────────────────────
    const scene  = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 100);
    camera.position.z = 2.2;

    // ── Renderer ───────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    // updateStyle=false: we control CSS ourselves to avoid overrides on resize
    renderer.setSize(W, H, false);
    renderer.setClearColor(0x000000, 0);
    Object.assign(renderer.domElement.style, {
      display:    "block",
      position:   "absolute",
      top:        "0",
      left:       "0",
      width:      "100%",
      height:     "100%",
      background: "transparent",
    });
    container.appendChild(renderer.domElement);

    // ── Particle geometry (pre-allocated, drawRange controls visible count) ─
    const ptPositions = new Float32Array(MAX_PARTICLES * 3);
    const ptPosAttr   = new THREE.BufferAttribute(ptPositions, 3);
    const ptGeo       = new THREE.BufferGeometry();
    ptGeo.setAttribute("position", ptPosAttr);
    ptGeo.setDrawRange(0, T.idle.particleCount);

    const ptUniforms = {
      ptSize:  { value: T.idle.pointSize },
      ptColor: { value: T.idle.colorParticle.clone() },
    };
    const ptMat  = new THREE.ShaderMaterial({
      vertexShader: PARTICLE_VERT, fragmentShader: PARTICLE_FRAG,
      uniforms: ptUniforms, transparent: true, depthWrite: false,
    });
    const ptMesh = new THREE.Points(ptGeo, ptMat);

    // ── Line geometry (pre-allocated, drawRange controls active segments) ──
    const linePositions = new Float32Array(MAX_LINE_VERTS * 3);
    const lineAlphas    = new Float32Array(MAX_LINE_VERTS);
    const linePosAttr   = new THREE.BufferAttribute(linePositions, 3);
    const lineAlpAttr   = new THREE.BufferAttribute(lineAlphas,    1);
    const lineGeo       = new THREE.BufferGeometry();
    lineGeo.setAttribute("position", linePosAttr);
    lineGeo.setAttribute("aAlpha",   lineAlpAttr);
    lineGeo.setDrawRange(0, 0);

    const lineUniforms = {
      lineColor:   { value: T.idle.colorLine.clone() },
      lineOpacity: { value: 0.6 },
    };
    const lineMat  = new THREE.ShaderMaterial({
      vertexShader: LINE_VERT, fragmentShader: LINE_FRAG,
      uniforms: lineUniforms, transparent: true, depthWrite: false,
    });
    const lineMesh = new THREE.LineSegments(lineGeo, lineMat);

    // ── Central luminous core ──────────────────────────────────────────────
    const coreGeo  = new THREE.SphereGeometry(0.07, 20, 16);
    const coreMat  = new THREE.MeshBasicMaterial({ color: T.idle.colorCore.clone() });
    const coreMesh = new THREE.Mesh(coreGeo, coreMat);

    // ── Group (single rotation transform for all meshes) ───────────────────
    const group = new THREE.Group();
    group.add(lineMesh, ptMesh, coreMesh);
    scene.add(group);

    // ── Idle halo billboard (AdditiveBlending, always faces camera) ────────
    const haloCanvas = document.createElement("canvas");
    haloCanvas.width = 128; haloCanvas.height = 128;
    const haloCtx = haloCanvas.getContext("2d")!;
    const haloGrad = haloCtx.createRadialGradient(64, 64, 0, 64, 64, 64);
    haloGrad.addColorStop(0,    "rgba(99,102,241,1)");
    haloGrad.addColorStop(0.45, "rgba(99,102,241,0.5)");
    haloGrad.addColorStop(1,    "rgba(99,102,241,0)");
    haloCtx.fillStyle = haloGrad;
    haloCtx.fillRect(0, 0, 128, 128);
    const haloTex = new THREE.CanvasTexture(haloCanvas);
    const haloMat = new THREE.SpriteMaterial({
      map: haloTex, blending: THREE.AdditiveBlending,
      transparent: true, opacity: 0, depthWrite: false,
    });
    const haloSprite = new THREE.Sprite(haloMat);
    haloSprite.scale.setScalar(4.0);
    scene.add(haloSprite);

    // ── Lerped state (mutated each frame) ──────────────────────────────────
    const cur = {
      particleCount:  T.idle.particleCount,
      radius:         T.idle.radius,
      connectionDist: T.idle.connectionDist,
      pointSize:      T.idle.pointSize,
      rotationSpeed:  T.idle.rotationSpeed,
      coreScale:      T.idle.coreScale,
      colorParticle:  T.idle.colorParticle.clone(),
      colorLine:      T.idle.colorLine.clone(),
      colorCore:      T.idle.colorCore.clone(),
    };

    // ── Resize ─────────────────────────────────────────────────────────────
    const ro = new ResizeObserver(() => {
      W = container.clientWidth;
      H = container.clientHeight;
      camera.aspect = W / H;
      camera.updateProjectionMatrix();
      renderer.setSize(W, H, false); // keep CSS at 100%×100%, only update framebuffer
    });
    ro.observe(container);

    // ── Animation loop ─────────────────────────────────────────────────────
    const clock = new THREE.Clock();
    let rafId   = 0;

    const animate = () => {
      rafId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();
      const tgt     = T[stateRef.current];
      const al      = audioLevelRef.current;

      // Lerp all values towards target
      cur.particleCount  = lerp(cur.particleCount,  tgt.particleCount,  0.04);
      cur.radius         = lerp(cur.radius,         tgt.radius,         0.04);
      cur.connectionDist = lerp(cur.connectionDist, tgt.connectionDist, 0.04);
      cur.pointSize      = lerp(cur.pointSize,      tgt.pointSize,      0.05);
      cur.rotationSpeed  = lerp(cur.rotationSpeed,  tgt.rotationSpeed,  0.04);
      cur.coreScale      = lerp(cur.coreScale,      tgt.coreScale,      0.04);
      cur.colorParticle.lerp(tgt.colorParticle, 0.04);
      cur.colorLine.lerp(tgt.colorLine,     0.04);
      cur.colorCore.lerp(tgt.colorCore,     0.04);

      const n      = Math.round(cur.particleCount);
      const radius = cur.radius * (1 + al * 0.15);   // audio: proportional sphere expansion
      const ptSize = cur.pointSize * (1 + al * 0.5); // audio: swells points
      const connD  = cur.connectionDist;
      const connD2 = connD * connD;

      // ── Update particle positions — organic per-particle oscillation ──────
      for (let i = 0; i < n; i++) {
        const breathe = Math.sin(elapsed * PARTICLE_FREQS[i] + PARTICLE_PHASES[i]) * PARTICLE_AMPS[i] * (1 + al * 3);
        const r       = radius + breathe;
        ptPositions[i * 3]     = BASE_DIRS[i * 3]     * r;
        ptPositions[i * 3 + 1] = BASE_DIRS[i * 3 + 1] * r;
        ptPositions[i * 3 + 2] = BASE_DIRS[i * 3 + 2] * r;
      }
      ptPosAttr.needsUpdate = true;
      ptGeo.setDrawRange(0, n);

      // ── Build line segments for nearby particle pairs ─────────────────────
      let vi = 0;
      outer: for (let i = 0; i < n - 1; i++) {
        const ax = ptPositions[i * 3];
        const ay = ptPositions[i * 3 + 1];
        const az = ptPositions[i * 3 + 2];
        for (let j = i + 1; j < n; j++) {
          if (vi >= MAX_LINE_VERTS - 1) break outer;
          const dx = ax - ptPositions[j * 3];
          const dy = ay - ptPositions[j * 3 + 1];
          const dz = az - ptPositions[j * 3 + 2];
          const d2 = dx * dx + dy * dy + dz * dz;
          if (d2 >= connD2) continue;
          const alpha = 1.0 - Math.sqrt(d2) / connD;
          const b = vi * 3;
          linePositions[b]     = ax;
          linePositions[b + 1] = ay;
          linePositions[b + 2] = az;
          lineAlphas[vi] = alpha;
          linePositions[b + 3] = ptPositions[j * 3];
          linePositions[b + 4] = ptPositions[j * 3 + 1];
          linePositions[b + 5] = ptPositions[j * 3 + 2];
          lineAlphas[vi + 1] = alpha;
          vi += 2;
        }
      }
      linePosAttr.needsUpdate = true;
      lineAlpAttr.needsUpdate = true;
      lineGeo.setDrawRange(0, vi);

      // ── Uniforms + core ───────────────────────────────────────────────────
      ptUniforms.ptSize.value = ptSize;
      ptUniforms.ptColor.value.copy(cur.colorParticle);
      lineUniforms.lineColor.value.copy(cur.colorLine);
      lineUniforms.lineOpacity.value = Math.min(1.0, 0.6 + al * 0.3);
      haloMat.opacity = lerp(haloMat.opacity, stateRef.current === "idle" ? 0.4 : 0.0, 0.04);
      coreMat.color.copy(cur.colorCore);
      coreMesh.scale.setScalar(cur.coreScale);

      // ── Group rotation ────────────────────────────────────────────────────
      group.rotation.y += cur.rotationSpeed;
      group.rotation.z += cur.rotationSpeed * 0.3;

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(rafId);
      ro.disconnect();
      renderer.dispose();
      ptGeo.dispose();   ptMat.dispose();
      lineGeo.dispose(); lineMat.dispose();
      coreGeo.dispose(); coreMat.dispose();
      haloTex.dispose(); haloMat.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return <div ref={containerRef} className="absolute inset-0" />;
}
