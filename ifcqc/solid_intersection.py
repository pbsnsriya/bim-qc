"""Double-precision booleans and bounded convex SAT. No geometry repair."""
from dataclasses import dataclass
import numpy as np

LINEAR_EPS_M=1e-9
VOLUME_EPS_M3=1e-15
MAX_CONVEX_FACES=512
MAX_SAT_AXES=10000

@dataclass
class SolidBody:
    vertices: np.ndarray
    faces: np.ndarray
    centre: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    solid: object
    normals: list | None
    edges: list | None

def _axes(vectors):
    result,seen=[],set()
    for vector in vectors:
        length=float(np.linalg.norm(vector))
        if length<=1e-12: continue
        axis=vector/length
        significant=np.flatnonzero(np.abs(axis)>1e-12)
        if axis[significant[0]]<0: axis=-axis
        key=tuple(np.round(axis,12))
        if key not in seen: seen.add(key); result.append(axis)
    return result

def _convex_features(vertices,faces):
    if len(faces)>MAX_CONVEX_FACES: return None,None
    triangles=vertices[faces]
    raw=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    normals=[]
    for triangle,normal in zip(triangles,raw):
        length=np.linalg.norm(normal)
        if length<=1e-15: return None,None
        normal=normal/length
        # All vertices must lie behind every outward boundary face. Cavities,
        # concavities and disconnected components do not become convex hulls.
        if np.max((vertices-triangle[0])@normal)>LINEAR_EPS_M: return None,None
        normals.append(normal)
    edges=[vertices[b]-vertices[a] for face in faces for a,b in
           [(face[0],face[1]),(face[1],face[2]),(face[2],face[0])]]
    return _axes(normals),_axes(edges)

def make_body(vertices,faces):
    import manifold3d as md
    vertices=np.asarray(vertices,dtype=np.float64)
    faces=np.asarray(faces,dtype=np.int64)
    if vertices.ndim!=2 or vertices.shape[1]!=3 or len(vertices)<4 or not np.isfinite(vertices).all():
        raise ValueError("No finite solid vertices supplied.")
    if faces.ndim!=2 or faces.shape[1]!=3 or len(faces)<4 or faces.min()<0 or faces.max()>=len(vertices):
        raise ValueError("Invalid solid triangle indices.")
    lower,upper=vertices.min(axis=0),vertices.max(axis=0)
    centre=lower+(upper-lower)/2
    local=np.ascontiguousarray(vertices-centre)
    solid=md.Manifold(md.Mesh64(local,np.ascontiguousarray(faces,dtype=np.uint64)))
    if solid.status()!=md.Error.NoError or solid.is_empty():
        raise ValueError(f"Solid Boolean input rejected: {solid.status()}. Geometry was not repaired.")
    if not np.isfinite(solid.volume()) or solid.volume()<=VOLUME_EPS_M3:
        raise ValueError("Solid volume is below the numerical evaluation limit.")
    normals,edges=_convex_features(local,faces)
    return SolidBody(local,faces,centre,lower,upper,solid,normals,edges)

def minimum_translation(first,second):
    """Shortest convex translation to boundary contact, including containment.

    SAT axes comprise face normals from both solids and nonparallel edge cross
    products. Interval overlap length alone is wrong for contained objects.
    """
    if first.normals is None or second.normals is None: return None
    if len(first.edges)*len(second.edges)+len(first.normals)+len(second.normals)>MAX_SAT_AXES: return None
    axes=_axes([*first.normals,*second.normals,
                *(np.cross(a,b) for a in first.edges for b in second.edges)])
    if len(axes)>MAX_SAT_AXES: return None
    a,b=first.vertices,second.vertices+(second.centre-first.centre)
    best=float('inf'); best_vector=None
    for axis in axes:
        pa,pb=a@axis,b@axis
        left,right=float(pa.max()-pb.min()),float(pb.max()-pa.min())
        if left<=LINEAR_EPS_M or right<=LINEAR_EPS_M:
            return {"distance_mm":0.,"translation_vector_metres":[0.,0.,0.]}
        distance=min(left,right)
        if distance<best:
            best=distance
            best_vector=(-axis*left) if left<=right else (axis*right)
    return {"distance_mm":best*1000,"translation_vector_metres":best_vector.tolist()}

def intersect_bodies(first,second):
    import manifold3d as md
    overlap=first.solid ^ second.solid.translate(tuple(second.centre-first.centre))
    if overlap.status()!=md.Error.NoError: raise ValueError(f"Solid intersection failed: {overlap.status()}.")
    volume=float(overlap.volume())
    if not np.isfinite(volume) or volume<0: raise ValueError("Intersection returned invalid volume.")
    if overlap.is_empty() or volume==0:
        return {"intersection_status":"no_positive_volume_intersection","intersection_volume_m3":0.,
                "minimum_translation_mm":None,"depth_status":"not_applicable"}
    if volume<=VOLUME_EPS_M3:
        return {"intersection_status":"below_numerical_volume_limit","intersection_volume_m3":volume,
                "minimum_translation_mm":None,"depth_status":"not_evaluated"}
    depth=minimum_translation(first,second)
    bounds=np.array(overlap.bounding_box()).reshape(2,3)+first.centre
    result={"intersection_status":"positive_volume_intersection","intersection_volume_m3":volume,
            "intersection_bounds_metres":bounds.tolist(),
            "minimum_translation_mm":depth['distance_mm'] if depth else None,
            "depth_status":"evaluated_convex_sat" if depth and depth['distance_mm']>0 else "not_evaluated"}
    if depth: result['translation_vector_metres']=depth['translation_vector_metres']
    return result
