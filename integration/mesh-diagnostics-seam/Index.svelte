<!-- frontend/Index.svelte -->
<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import * as THREE from 'three';
    import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';

    // Core Gradio component props
    export let value: {
        vertices: number[];      // Flat float array: [x1, y1, z1, x2, y2, z2, ...]
        faces: number[];         // Flat index array: [f1_v1, f1_v2, f1_v3, ...]
        error_edges?: number[][]; // Array of edge coordinate pairs: [[x1,y1,z1, x2,y2,z2], ...]
        metrics?: { label: string; value: string | number; status: 'pass' | 'fail' }[];
    };
    export let el: HTMLElement;
    export let gradio: any;

    // DOM Bindings
    let canvasContainer: HTMLDivElement;
    let resizeObserver: ResizeObserver;

    // Three.js Core Instances
    let scene: THREE.Scene;
    let camera: THREE.PerspectiveCamera;
    let renderer: THREE.WebGLRenderer;
    let controls: OrbitControls;
    let animationFrameId: number;

    // Geometry Instances (for dynamic cleanup)
    let meshGroup = new THREE.Group();

    function initThree() {
        if (!canvasContainer || !value) return;

        // 1. Initialize Scene & Clean Engineering Slate Background
        scene = new THREE.Scene();
        scene.background = new THREE.Color('#fafafa');
        scene.add(meshGroup);

        // 2. Camera Setup Setup
        const width = canvasContainer.clientWidth;
        const height = canvasContainer.clientHeight || 450;
        camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
        camera.position.set(30, 30, 40);

        // 3. Hardware Accelerated Renderer
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        canvasContainer.appendChild(renderer.domElement);

        // 4. Industrial Lighting Rig
        const ambientLight = new THREE.AmbientLight('#ffffff', 0.6);
        scene.add(ambientLight);

        const keyLight = new THREE.DirectionalLight('#ffffff', 0.7);
        keyLight.position.set(100, 150, 50);
        scene.add(keyLight);

        const fillLight = new THREE.DirectionalLight('#cbd5e1', 0.4);
        fillLight.position.set(-100, -50, -50);
        scene.add(fillLight);

        // 5. Orbit Interaction Controls
        controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;

        // 6. Build the CAD / FEM Elements
        buildGeometry();

        // 7. Start Animation Core Loop
        function animate() {
            animationFrameId = requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        }
        animate();

        // 8. Handle Container Resizing Fluidly
        resizeObserver = new ResizeObserver((entries) => {
            for (let entry of entries) {
                const w = entry.contentRect.width;
                const h = entry.contentRect.height || 450;
                camera.aspect = w / h;
                camera.updateProjectionMatrix();
                renderer.setSize(w, h);
            }
        });
        resizeObserver.observe(canvasContainer);
    }

    function buildGeometry() {
        // Clear previous runs
        while(meshGroup.children.length > 0){
            meshGroup.remove(meshGroup.children[0]);
        }

        if (!value.vertices || !value.faces) return;

        // --- PART A: The Transparent Base Ghost Shell ---
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(value.vertices, 3));
        geometry.setIndex(value.faces);
        geometry.computeVertexNormals();

        // High-performance semi-transparent material mapping structural volume
        const transparentShellMat = new THREE.MeshStandardMaterial({
            color: '#64748b',       // Clean blueprint gray
            transparent: true,
            opacity: 0.25,
            roughness: 0.3,
            metalness: 0.1,
            side: THREE.DoubleSide
        });

        const shellMesh = new THREE.Mesh(geometry, transparentShellMat);
        meshGroup.add(shellMesh);

        // Subdued baseline wireframe structure
        const wireframeGeom = new THREE.WireframeGeometry(geometry);
        const wireframeMat = new THREE.LineBasicMaterial({ color: '#cbd5e1', transparent: true, opacity: 0.4 });
        const wireframe = new THREE.LineSegments(wireframeGeom, wireframeMat);
        meshGroup.add(wireframe);

        // --- PART B: High-Contrast Neon Error Overlays ---
        if (value.error_edges && value.error_edges.length > 0) {
            // Neon pink/magenta material indicating validation failure curves
            const errorLineMat = new THREE.LineBasicMaterial({
                color: '#f43f5e',
                linewidth: 2,
                depthTest: false // Renders overlay on top of solid faces cleanly
            });

            value.error_edges.forEach(edgeCoords => {
                // edgeCoords format: [x1, y1, z1, x2, y2, z2]
                const points = [
                    new THREE.Vector3(edgeCoords[0], edgeCoords[1], edgeCoords[2]),
                    new THREE.Vector3(edgeCoords[3], edgeCoords[4], edgeCoords[5])
                ];
                const edgeGeom = new THREE.BufferGeometry().setFromPoints(points);
                const lineSegment = new THREE.Line(edgeGeom, errorLineMat);
                lineSegment.renderOrder = 1; // Force layer prioritization
                meshGroup.add(lineSegment);
            });
        }

        // Center camera automatically on the lightweight asset coordinates
        geometry.computeBoundingSphere();
        const sphere = geometry.boundingSphere;
        if (sphere) {
            controls.target.copy(sphere.center);
            camera.position.set(sphere.center.x + sphere.radius * 2, sphere.center.y + sphere.radius * 2, sphere.center.z + sphere.radius * 2);
            controls.update();
        }
    }

    // Reactively refresh layout if model value object changes via Gradio pipeline updates
    $: if (scene && value) {
        buildGeometry();
    }

    onMount(() => {
        initThree();
    });

    onDestroy(() => {
        if (animationFrameId) cancelAnimationFrame(animationFrameId);
        if (resizeObserver) resizeObserver.disconnect();
        if (controls) controls.dispose();
        if (renderer) renderer.dispose();
    });
</script>

<!-- Split-Pane Split Screen Layout Layout (60% WebGL Viewer / 40% Dense Diagnostic Audit) -->
<div class="grid grid-cols-1 lg:grid-cols-5 border border-slate-200 rounded-md overflow-hidden bg-white shadow-sm max-w-full font-sans text-sm">

    <!-- 3D Interactive WebGL Window -->
    <div class="lg:col-span-3 h-[450px] relative bg-slate-50 border-r border-slate-200" bind:this={canvasContainer}>
        {#if value?.error_edges && value.error_edges.length > 0}
            <div class="absolute top-3 left-3 bg-rose-50 border border-rose-200 px-2 py-1 text-xs rounded text-rose-700 font-medium z-10 shadow-sm animate-pulse">
                ⚠️ {value.error_edges.length} Discontinuity Overlays Active
            </div>
        {/if}
    </div>

    <!-- Dense Technical Engineering Audit Panel -->
    <div class="lg:col-span-2 flex flex-col h-[450px]">
        <div class="bg-slate-50 px-4 py-2.5 border-b border-slate-200 font-semibold text-slate-700 tracking-wide text-xs uppercase">
            Topological Validation Log
        </div>
        <div class="overflow-y-auto flex-1 divide-y divide-slate-100">
            {#if value?.metrics && value.metrics.length > 0}
                {#each value.metrics as metric}
                    <div class="px-4 py-3 flex items-center justify-between transition-colors hover:bg-slate-50/50">
                        <span class="font-medium text-slate-600">{metric.label}</span>
                        <div class="flex items-center gap-2">
                            <span class="font-mono text-slate-900 bg-slate-100 px-1.5 py-0.5 rounded text-xs font-semibold">{metric.value}</span>
                            {#if metric.status === 'pass'}
                                <span class="text-emerald-600 text-xs font-bold font-mono">✓</span>
                            {:else}
                                <span class="text-rose-600 text-xs font-bold font-mono">𐄂</span>
                            {/if}
                        </div>
                    </div>
                {/each}
            {:else}
                <div class="p-8 text-center text-slate-400 italic">No diagnostic telemetry attached.</div>
            {/if}
        </div>
    </div>
</div>

<style>
    :global(.canvas-container canvas) {
        display: block;
        width: 100% !important;
        height: 100% !important;
    }
</style>
