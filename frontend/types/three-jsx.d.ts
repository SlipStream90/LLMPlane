/* eslint-disable @typescript-eslint/no-empty-object-type */
import type { ThreeElement } from "@react-three/fiber";
import type * as THREE from "three";

declare module "react" {
  namespace JSX {
    interface IntrinsicElements extends ThreeElements {}
  }
}

interface ThreeElements {
  group: ThreeElement<typeof THREE.Group>;
  mesh: ThreeElement<typeof THREE.Mesh>;
  ambientLight: ThreeElement<typeof THREE.AmbientLight>;
  pointLight: ThreeElement<typeof THREE.PointLight>;
  directionalLight: ThreeElement<typeof THREE.DirectionalLight>;
  spotLight: ThreeElement<typeof THREE.SpotLight>;
  rectAreaLight: ThreeElement<typeof THREE.RectAreaLight>;
  hemisphereLight: ThreeElement<typeof THREE.HemisphereLight>;
  camera: ThreeElement<typeof THREE.Camera>;
  orthographicCamera: ThreeElement<typeof THREE.OrthographicCamera>;
  perspectiveCamera: ThreeElement<typeof THREE.PerspectiveCamera>;
  primitive: { object: THREE.Object3D } & Record<string, unknown>;
  line: ThreeElement<typeof THREE.Line>;
  lineSegments: ThreeElement<typeof THREE.LineSegments>;
  meshBasicMaterial: ThreeElement<typeof THREE.MeshBasicMaterial>;
  meshStandardMaterial: ThreeElement<typeof THREE.MeshStandardMaterial>;
  meshPhysicalMaterial: ThreeElement<typeof THREE.MeshPhysicalMaterial>;
  meshPhongMaterial: ThreeElement<typeof THREE.MeshPhongMaterial>;
  meshLambertMaterial: ThreeElement<typeof THREE.MeshLambertMaterial>;
  boxGeometry: ThreeElement<typeof THREE.BoxGeometry>;
  sphereGeometry: ThreeElement<typeof THREE.SphereGeometry>;
  planeGeometry: ThreeElement<typeof THREE.PlaneGeometry>;
  cylinderGeometry: ThreeElement<typeof THREE.CylinderGeometry>;
  torusGeometry: ThreeElement<typeof THREE.TorusGeometry>;
  circleGeometry: ThreeElement<typeof THREE.CircleGeometry>;
  coneGeometry: ThreeElement<typeof THREE.ConeGeometry>;
  ringGeometry: ThreeElement<typeof THREE.RingGeometry>;
}
