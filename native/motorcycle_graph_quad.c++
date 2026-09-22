#include <iostream>
#include <vector>
#include <cmath>
#include <queue>
#include <map>
#include <memory>
#include <algorithm>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <limits>
#include <string>

// Global constants and numerical tolerance
constexpr double EPSILON = 1e-9;
constexpr double PI = 3.14159265358979323846;

struct Vector3 {
    double x, y, z;

    Vector3() : x(0), y(0), z(0) {}
    Vector3(double x_, double y_, double z_) : x(x_), y(y_), z(z_) {}

    Vector3 operator+(const Vector3& o) const { return Vector3(x + o.x, y + o.y, z + o.z); }
    Vector3 operator-(const Vector3& o) const { return Vector3(x - o.x, y - o.y, z - o.z); }
    Vector3 operator*(double s) const { return Vector3(x * s, y * s, z * s); }
    Vector3 operator/(double s) const { return Vector3(x / s, y / s, z / s); }

    double dot(const Vector3& o) const { return x * o.x + y * o.y + z * o.z; }
    Vector3 cross(const Vector3& o) const {
        return Vector3(
            y * o.z - z * o.y,
            z * o.x - x * o.z,
            x * o.y - y * o.x
        );
    }

    double norm() const { return std::sqrt(dot(*this)); }
    Vector3 normalized() const {
        double n = norm();
        return (n > EPSILON) ? (*this / n) : Vector3(0, 0, 0);
    }
};

struct Vector2 {
    double x, y;

    Vector2() : x(0), y(0) {}
    Vector2(double x_, double y_) : x(x_), y(y_) {}

    Vector2 operator+(const Vector2& o) const { return Vector2(x + o.x, y + o.y); }
    Vector2 operator-(const Vector2& o) const { return Vector2(x - o.x, y - o.y); }
    Vector2 operator*(double s) const { return Vector2(x * s, y * s); }
    Vector2 operator/(double s) const { return Vector2(x / s, y / s); }

    double dot(const Vector2& o) const { return x * o.x + y * o.y; }
    double cross(const Vector2& o) const { return x * o.y - y * o.x; }

    double norm() const { return std::sqrt(dot(*this)); }
    Vector2 normalized() const {
        double n = norm();
        return (n > EPSILON) ? (*this / n) : Vector2(0, 0);
    }
};

struct Segment2DIntersection {
    bool intersects;
    double t_first;  // Parameter along first segment [0, 1]
    double t_second; // Parameter along second segment [0, 1]
    Vector2 point;
};

// Computes robust segment-segment intersection in local 2D tangent space
Segment2DIntersection intersect_segments_2d(const Vector2& p1, const Vector2& p2,
                                            const Vector2& q1, const Vector2& q2) {
    Vector2 u = p2 - p1;
    Vector2 v = q2 - q1;
    double det = u.cross(v);

    Segment2DIntersection result{false, 0.0, 0.0, Vector2(0, 0)};

    if (std::abs(det) < EPSILON) {
        return result;
    }

    Vector2 w = p1 - q1;
    double t = v.cross(w) / det;
    double s = u.cross(w) / det;

    if (t >= -EPSILON && t <= 1.0 + EPSILON && s >= -EPSILON && s <= 1.0 + EPSILON) {
        result.intersects = true;
        result.t_first = std::clamp(t, 0.0, 1.0);
        result.t_second = std::clamp(s, 0.0, 1.0);
        result.point = p1 + u * result.t_first;
    }

    return result;
}

struct MeshEdge {
    int id;
    int v0, v1;           // Vertex indices (v0 < v1)
    int face_left;        // Primary face (-1 if boundary)
    int face_right;       // Neighbor face (-1 if boundary)
    double length;
};

struct MeshFace {
    int id;
    std::vector<int> v;             // Vertices in counter-clockwise order (e.g. 4 for quad)
    std::vector<int> e;             // Edges corresponding to (v0-v1), (v1-v2), ..., (vN-v0)
    Vector3 normal;
    
    // 2D flattened local coordinate layout for intrinsic geodesic unfolding
    std::vector<Vector2> v_2d;
};

struct MeshVertex {
    int id;
    Vector3 pos;
    std::vector<int> incident_faces;
    std::vector<int> incident_edges;
};

class PolygonalMesh {
public:
    std::vector<MeshVertex> vertices;
    std::vector<MeshEdge> edges;
    std::vector<MeshFace> faces;
    std::map<std::pair<int, int>, int> edge_lookup;

    void add_vertex(const Vector3& p) {
        MeshVertex v;
        v.id = static_cast<int>(vertices.size());
        v.pos = p;
        vertices.push_back(v);
    }

    int get_or_create_edge(int v0, int v1, int face_id) {
        int a = std::min(v0, v1);
        int b = std::max(v0, v1);
        auto key = std::make_pair(a, b);

        if (edge_lookup.count(key)) {
            int e_id = edge_lookup[key];
            if (edges[e_id].v0 == v0) {
                edges[e_id].face_left = face_id;
            } else {
                edges[e_id].face_right = face_id;
            }
            return e_id;
        }

        MeshEdge e;
        e.id = static_cast<int>(edges.size());
        e.v0 = v0;
        e.v1 = v1;
        e.face_left = face_id;
        e.face_right = -1;
        e.length = (vertices[v1].pos - vertices[v0].pos).norm();

        edges.push_back(e);
        edge_lookup[key] = e.id;

        vertices[v0].incident_edges.push_back(e.id);
        vertices[v1].incident_edges.push_back(e.id);

        return e.id;
    }

    void add_face(const std::vector<int>& vert_indices) {
        MeshFace f;
        f.id = static_cast<int>(faces.size());
        f.v = vert_indices;
        size_t n = vert_indices.size();

        // Calculate face normal using Newell's method for arbitrary quad / polygon
        Vector3 normal(0, 0, 0);
        for (size_t i = 0; i < n; ++i) {
            const Vector3& current = vertices[vert_indices[i]].pos;
            const Vector3& next = vertices[vert_indices[(i + 1) % n]].pos;
            normal.x += (current.y - next.y) * (current.z + next.z);
            normal.y += (current.z - next.z) * (current.x + next.x);
            normal.z += (current.x - next.x) * (current.y + next.y);
        }
        f.normal = normal.normalized();

        // Register edges
        f.e.resize(n);
        for (size_t i = 0; i < n; ++i) {
            f.e[i] = get_or_create_edge(vert_indices[i], vert_indices[(i + 1) % n], f.id);
        }

        // Project 3D vertices onto local 2D tangent plane for intrinsic unfolding
        Vector3 origin = vertices[vert_indices[0]].pos;
        Vector3 u_axis = (vertices[vert_indices[1]].pos - origin).normalized();
        Vector3 v_axis = f.normal.cross(u_axis).normalized();

        f.v_2d.resize(n);
        for (size_t i = 0; i < n; ++i) {
            Vector3 diff = vertices[vert_indices[i]].pos - origin;
            f.v_2d[i] = Vector2(diff.dot(u_axis), diff.dot(v_axis));
        }

        faces.push_back(f);

        for (int v_id : vert_indices) {
            vertices[v_id].incident_faces.push_back(f.id);
        }
    }

    // Convert local 2D face point to global 3D space using local tangent basis
    Vector3 map_2d_to_3d(int face_id, const Vector2& p2d) const {
        const MeshFace& f = faces[face_id];
        Vector3 origin = vertices[f.v[0]].pos;
        Vector3 u_axis = (vertices[f.v[1]].pos - origin).normalized();
        Vector3 v_axis = f.normal.cross(u_axis).normalized();

        return origin + u_axis * p2d.x + v_axis * p2d.y;
    }

    // Get adjacent face across a shared edge
    int get_adjacent_face(int current_face, int edge_id) const {
        const MeshEdge& e = edges[edge_id];
        if (e.face_left == current_face) return e.face_right;
        if (e.face_right == current_face) return e.face_left;
        return -1;
    }
};

struct TrailSegment {
    int motorcycle_id;
    int face_id;
    Vector2 start_2d;
    Vector2 end_2d;
    Vector3 start_3d;
    Vector3 end_3d;
    double start_time;
    double end_time;
};

struct Motorcycle {
    int id;
    int current_face;
    Vector2 pos_2d;          // Current position in face 2D space
    Vector2 dir_2d;          // Current velocity direction (unit vector)
    double speed;            // Distance traversed per time unit
    double time;             // Total travel time elapsed
    bool active;             // Active or crashed
};

enum class EventType {
    EDGE_CROSSING,
    CRASH
};

struct Event {
    EventType type;
    double time;
    int motorcycle_id;
    int target_face;
    int exit_edge;
    Vector2 exit_pos_2d;
    Vector2 enter_pos_2d;
    Vector2 enter_dir_2d;
    int crashed_into_mc_id;

    // Min-heap ordering for priority queue
    bool operator>(const Event& o) const {
        return time > o.time;
    }
};

class MotorcycleGraphBuilder {
private:
    const PolygonalMesh& mesh;
    std::vector<Motorcycle> motorcycles;
    std::vector<TrailSegment> all_trails;
    std::map<int, std::vector<int>> face_trails;
    std::priority_queue<Event, std::vector<Event>, std::greater<Event>> event_queue;

public:
    MotorcycleGraphBuilder(const PolygonalMesh& m) : mesh(m) {}

    int add_motorcycle(int start_vertex_id, int face_id, double angle_rad, double speed = 1.0) {
        const MeshFace& f = mesh.faces[face_id];
        
        int local_idx = -1;
        for (size_t i = 0; i < f.v.size(); ++i) {
            if (f.v[i] == start_vertex_id) {
                local_idx = static_cast<int>(i);
                break;
            }
        }
        if (local_idx == -1) return -1;

        Motorcycle mc;
        mc.id = static_cast<int>(motorcycles.size());
        mc.current_face = face_id;
        mc.pos_2d = f.v_2d[local_idx];
        
        // Offset slightly inwards toward quad centroid
        Vector2 center_2d(0, 0);
        for (const auto& v2 : f.v_2d) {
            center_2d = center_2d + v2;
        }
        center_2d = center_2d / static_cast<double>(f.v.size());

        Vector2 inwards = (center_2d - mc.pos_2d).normalized() * (EPSILON * 100.0);
        mc.pos_2d = mc.pos_2d + inwards;

        size_t n = f.v.size();
        Vector2 base_dir = (f.v_2d[(local_idx + 1) % n] - f.v_2d[local_idx]).normalized();
        double cos_a = std::cos(angle_rad);
        double sin_a = std::sin(angle_rad);
        mc.dir_2d = Vector2(
            base_dir.x * cos_a - base_dir.y * sin_a,
            base_dir.x * sin_a + base_dir.y * cos_a
        ).normalized();

        mc.speed = speed;
        mc.time = 0.0;
        mc.active = true;

        motorcycles.push_back(mc);
        schedule_next_event(mc.id);

        return mc.id;
    }

    void schedule_next_event(int mc_id) {
        Motorcycle& mc = motorcycles[mc_id];
        if (!mc.active) return;

        const MeshFace& f = mesh.faces[mc.current_face];

        // 1. Check for collision with existing trail walls inside current polygon
        double min_crash_time = std::numeric_limits<double>::infinity();
        Vector2 crash_pos_2d(0, 0);
        int crashed_into_id = -1;

        if (face_trails.count(f.id)) {
            for (int trail_idx : face_trails[f.id]) {
                const TrailSegment& existing = all_trails[trail_idx];
                
                if (existing.motorcycle_id == mc.id && existing.start_time >= mc.time) continue;

                auto inter = intersect_segments_2d(
                    mc.pos_2d, mc.pos_2d + mc.dir_2d * 1e6,
                    existing.start_2d, existing.end_2d
                );

                if (inter.intersects) {
                    double dist = (inter.point - mc.pos_2d).norm();
                    double travel_time = dist / mc.speed;
                    double arrival_time = mc.time + travel_time;

                    double wall_creation_time = existing.start_time + inter.t_second * (existing.end_time - existing.start_time);
                    if (arrival_time >= wall_creation_time - EPSILON) {
                        if (travel_time > EPSILON && arrival_time < min_crash_time) {
                            min_crash_time = arrival_time;
                            crash_pos_2d = inter.point;
                            crashed_into_id = existing.motorcycle_id;
                        }
                    }
                }
            }
        }

        // 2. Compute intersection with polygon bounding edges
        double min_edge_dist = std::numeric_limits<double>::infinity();
        Vector2 edge_exit_2d(0, 0);
        int hit_edge_id = -1;

        size_t num_edges = f.v.size();
        for (size_t i = 0; i < num_edges; ++i) {
            Vector2 e1 = f.v_2d[i];
            Vector2 e2 = f.v_2d[(i + 1) % num_edges];

            auto inter = intersect_segments_2d(
                mc.pos_2d, mc.pos_2d + mc.dir_2d * 1e6,
                e1, e2
            );

            if (inter.intersects) {
                double dist = (inter.point - mc.pos_2d).norm();
                if (dist > EPSILON && dist < min_edge_dist) {
                    min_edge_dist = dist;
                    edge_exit_2d = inter.point;
                    hit_edge_id = f.e[i];
                }
            }
        }

        double edge_travel_time = min_edge_dist / mc.speed;
        double edge_crossing_time = mc.time + edge_travel_time;

        if (min_crash_time < edge_crossing_time) {
            Event ev;
            ev.type = EventType::CRASH;
            ev.time = min_crash_time;
            ev.motorcycle_id = mc_id;
            ev.exit_pos_2d = crash_pos_2d;
            ev.crashed_into_mc_id = crashed_into_id;
            event_queue.push(ev);
            return;
        }

        if (hit_edge_id != -1 && edge_crossing_time < std::numeric_limits<double>::infinity()) {
            int next_face = mesh.get_adjacent_face(mc.current_face, hit_edge_id);

            Event ev;
            ev.type = EventType::EDGE_CROSSING;
            ev.time = edge_crossing_time;
            ev.motorcycle_id = mc_id;
            ev.target_face = next_face;
            ev.exit_edge = hit_edge_id;
            ev.exit_pos_2d = edge_exit_2d;

            if (next_face != -1) {
                const MeshFace& f_next = mesh.faces[next_face];

                Vector2 e_start = f.v_2d[0];
                Vector2 e_end = f.v_2d[1];
                for (size_t i = 0; i < f.v.size(); ++i) {
                    if (f.e[i] == hit_edge_id) {
                        e_start = f.v_2d[i];
                        e_end = f.v_2d[(i + 1) % f.v.size()];
                        break;
                    }
                }

                double edge_len = (e_end - e_start).norm();
                double param = (edge_exit_2d - e_start).norm() / edge_len;
                param = std::clamp(param, 0.0, 1.0);

                Vector2 n_start = f_next.v_2d[0];
                Vector2 n_end = f_next.v_2d[1];
                for (size_t i = 0; i < f_next.v.size(); ++i) {
                    if (f_next.e[i] == hit_edge_id) {
                        n_start = f_next.v_2d[(i + 1) % f_next.v.size()];
                        n_end = f_next.v_2d[i];
                        break;
                    }
                }

                ev.enter_pos_2d = n_start + (n_end - n_start) * param;

                Vector2 edge_dir_curr = (e_end - e_start).normalized();
                Vector2 edge_dir_next = (n_end - n_start).normalized();

                double cos_e = mc.dir_2d.dot(edge_dir_curr);
                double sin_e = mc.dir_2d.cross(edge_dir_curr);

                ev.enter_dir_2d = Vector2(
                    edge_dir_next.x * cos_e + edge_dir_next.y * sin_e,
                    -edge_dir_next.x * sin_e + edge_dir_next.y * cos_e
                ).normalized();
            }

            event_queue.push(ev);
        }
    }

    void run_simulation() {
        std::cout << "\n======================================================\n";
        std::cout << " Starting Motorcycle Graph Simulation Queue Processing \n";
        std::cout << " Initial active motorcycles: " << motorcycles.size() << "\n";
        std::cout << "======================================================\n";

        int event_count = 0;

        while (!event_queue.empty()) {
            Event ev = event_queue.top();
            event_queue.pop();

            Motorcycle& mc = motorcycles[ev.motorcycle_id];
            if (!mc.active) continue; // Motorcycle already stopped

            event_count++;

            // Record trail segment traversed in current face
            TrailSegment trail;
            trail.motorcycle_id = mc.id;
            trail.face_id = mc.current_face;
            trail.start_2d = mc.pos_2d;
            trail.end_2d = ev.exit_pos_2d;
            trail.start_3d = mesh.map_2d_to_3d(mc.current_face, mc.pos_2d);
            trail.end_3d = mesh.map_2d_to_3d(mc.current_face, ev.exit_pos_2d);
            trail.start_time = mc.time;
            trail.end_time = ev.time;

            all_trails.push_back(trail);
            face_trails[mc.current_face].push_back(static_cast<int>(all_trails.size()) - 1);

            if (ev.type == EventType::CRASH) {
                mc.active = false;
                mc.time = ev.time;
                mc.pos_2d = ev.exit_pos_2d;
                std::cout << " [Event " << event_count << "] t=" << std::fixed << std::setprecision(4)
                          << ev.time << " | Motorcycle #" << mc.id << " CRASHED into Motorcycle #"
                          << ev.crashed_into_mc_id << " inside Face " << mc.current_face << "\n";
            } else if (ev.type == EventType::EDGE_CROSSING) {
                if (ev.target_face == -1) {
                    // Hit mesh boundary
                    mc.active = false;
                    mc.time = ev.time;
                    mc.pos_2d = ev.exit_pos_2d;
                    std::cout << " [Event " << event_count << "] t=" << std::fixed << std::setprecision(4)
                              << ev.time << " | Motorcycle #" << mc.id << " REACHED MESH BOUNDARY at Edge "
                              << ev.exit_edge << "\n";
                } else {
                    // Transition to next face
                    mc.current_face = ev.target_face;
                    mc.pos_2d = ev.enter_pos_2d;
                    mc.dir_2d = ev.enter_dir_2d;
                    mc.time = ev.time;

                    // Schedule next propagation step
                    schedule_next_event(mc.id);
                }
            }
        }

        std::cout << " Simulation finished. Total graph segments generated: " << all_trails.size() << "\n\n";
    }

    void export_to_obj(const std::string& filename) const {
        std::ofstream out(filename);
        if (!out.is_open()) {
            std::cerr << "Failed to open file for export: " << filename << "\n";
            return;
        }

        out << "# Motorcycle Graph Generated Mesh & Trails\n";
        out << "# Base Mesh Vertices\n";

        for (const auto& v : mesh.vertices) {
            out << "v " << v.pos.x << " " << v.pos.y << " " << v.pos.z << "\n";
        }

        out << "\n# Base Mesh Faces\n";
        for (const auto& f : mesh.faces) {
            out << "f";
            for (int v_idx : f.v) {
                out << " " << (v_idx + 1);
            }
            out << "\n";
        }

        out << "\n# Motorcycle Graph Trail Segments (Lines)\n";
        int v_offset = static_cast<int>(mesh.vertices.size()) + 1;

        for (const auto& trail : all_trails) {
            out << "v " << trail.start_3d.x << " " << trail.start_3d.y << " " << trail.start_3d.z << "\n";
            out << "v " << trail.end_3d.x << " " << trail.end_3d.y << " " << trail.end_3d.z << "\n";
            out << "l " << v_offset << " " << (v_offset + 1) << "\n";
            v_offset += 2;
        }

        out.close();
        std::cout << " Successfully exported Motorcycle Graph model to: " << filename << "\n";
    }

    void print_summary() const {
        std::cout << "======================================================\n";
        std::cout << "                MOTORCYCLE GRAPH SUMMARY              \n";
        std::cout << "======================================================\n";
        std::cout << " Total Motorcycles Run : " << motorcycles.size() << "\n";
        std::cout << " Total Graph Segments  : " << all_trails.size() << "\n";
        
        for (const auto& mc : motorcycles) {
            std::cout << " Motorcycle #" << mc.id << ": Active=" << (mc.active ? "Yes" : "Crashed/Stopped")
                      << " | Final Time=" << mc.time << " | Final Face=" << mc.current_face << "\n";
        }
        std::cout << "======================================================\n";
    }
};

PolygonalMesh create_quad_torus_mesh(double r_major = 2.5, double r_minor = 1.0, int n_major = 12, int n_minor = 8) {
    PolygonalMesh mesh;

    for (int i = 0; i < n_major; ++i) {
        double u = i * 2.0 * PI / n_major;
        double cos_u = std::cos(u);
        double sin_u = std::sin(u);

        for (int j = 0; j < n_minor; ++j) {
            double v = j * 2.0 * PI / n_minor;
            double cos_v = std::cos(v);
            double sin_v = std::sin(v);

            double x = (r_major + r_minor * cos_v) * cos_u;
            double y = (r_major + r_minor * cos_v) * sin_u;
            double z = r_minor * sin_v;

            mesh.add_vertex(Vector3(x, y, z));
        }
    }

    for (int i = 0; i < n_major; ++i) {
        int i_next = (i + 1) % n_major;
        for (int j = 0; j < n_minor; ++j) {
            int j_next = (j + 1) % n_minor;

            int v0 = i * n_minor + j;
            int v1 = i_next * n_minor + j;
            int v2 = i_next * n_minor + j_next;
            int v3 = i * n_minor + j_next;

            // Add 4-sided Quad face
            mesh.add_face({v0, v1, v2, v3});
        }
    }

    return mesh;
}

PolygonalMesh create_quad_cube_mesh(double side = 2.0) {
    PolygonalMesh mesh;
    double h = side / 2.0;

    // 8 vertices of a cube
    mesh.add_vertex(Vector3(-h, -h, -h)); // 0
    mesh.add_vertex(Vector3( h, -h, -h)); // 1
    mesh.add_vertex(Vector3( h,  h, -h)); // 2
    mesh.add_vertex(Vector3(-h,  h, -h)); // 3
    mesh.add_vertex(Vector3(-h, -h,  h)); // 4
    mesh.add_vertex(Vector3( h, -h,  h)); // 5
    mesh.add_vertex(Vector3( h,  h,  h)); // 6
    mesh.add_vertex(Vector3(-h,  h,  h)); // 7

    // 6 quad faces
    mesh.add_face({0, 3, 2, 1}); // Bottom (-Z)
    mesh.add_face({4, 5, 6, 7}); // Top (+Z)
    mesh.add_face({0, 1, 5, 4}); // Front (-Y)
    mesh.add_face({2, 3, 7, 6}); // Back (+Y)
    mesh.add_face({0, 4, 7, 3}); // Left (-X)
    mesh.add_face({1, 2, 6, 5}); // Right (+X)

    return mesh;
}

int main() {
    std::cout << "======================================================\n";
    std::cout << "     3D Motorcycle Graph Construction on Quad Mesh    \n";
    std::cout << "======================================================\n";

    // 1. Construct Quad Torus Mesh
    std::cout << " Building Quad Torus mesh...\n";
    PolygonalMesh quad_torus = create_quad_torus_mesh(2.5, 1.0, 16, 12);
    std::cout << " Mesh built with " << quad_torus.vertices.size() << " vertices, "
              << quad_torus.faces.size() << " quad faces, " << quad_torus.edges.size() << " edges.\n";

    MotorcycleGraphBuilder builder(quad_torus);

    std::cout << " Initializing seed motorcycles on Quad Torus...\n";
    builder.add_motorcycle(0, 0, 0.25 * PI, 1.0);
    builder.add_motorcycle(10, 15, 0.75 * PI, 1.0);
    builder.add_motorcycle(25, 35, 1.25 * PI, 1.0);
    builder.add_motorcycle(40, 55, 1.75 * PI, 1.0);

    builder.run_simulation();
    builder.print_summary();
    builder.export_to_obj("motorcycle_graph_quad_torus.obj");

    // 2. Construct Quad Cube Mesh
    std::cout << "\n Running test case 2: Quad Cube Mesh...\n";
    PolygonalMesh quad_cube = create_quad_cube_mesh(3.0);
    MotorcycleGraphBuilder cube_builder(quad_cube);

    cube_builder.add_motorcycle(0, 0, 0.2 * PI, 1.0);
    cube_builder.add_motorcycle(2, 2, 0.7 * PI, 1.0);
    cube_builder.add_motorcycle(5, 4, 1.1 * PI, 1.0);

    cube_builder.run_simulation();
    cube_builder.export_to_obj("motorcycle_graph_quad_cube.obj");

    std::cout << "\nQuad mesh motorcycle graph simulation completed successfully.\n";
    return 0;
}