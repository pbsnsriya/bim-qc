"""Bounded Stage 3 pilot: IFC bodies, solid intersections and convex SAT depth."""
from datetime import datetime,timezone
from pathlib import Path
from hashlib import sha256
from importlib.metadata import version
from math import isfinite
from time import perf_counter
from .geometry_checks import STRUCTURAL_CLASSES,_pair_issue
from .solid_intersection import make_body,intersect_bodies,LINEAR_EPS_M,VOLUME_EPS_M3
from .version import APP_VERSION

MAX_ELEMENTS=100
MAX_TRIANGLES=200_000
MAX_PAIRS=2500
NUMERIC_SLACK_MM=LINEAR_EPS_M*1000

def run_hard_clash_model(model,tolerance_mm=2.,element_ids=None):
    import ifcopenshell
    import ifcopenshell.geom
    import numpy as np
    if type(tolerance_mm) is bool or not isinstance(tolerance_mm,(int,float)) or not isfinite(tolerance_mm) or not 0<=tolerance_mm<=1000:
        raise ValueError('Hard-clash threshold must be a finite number from 0 to 1000 mm.')
    eligible={e.id():e for e in model.by_type('IfcDistributionElement')}
    for cls in STRUCTURAL_CLASSES: eligible.update({e.id():e for e in model.by_type(cls)})
    if element_ids is not None:
        if not isinstance(element_ids,list) or not element_ids or any(type(i) is not int or i<=0 for i in element_ids):
            raise ValueError('Element IDs must be a non-empty list of positive integers.')
        invalid=sorted(set(element_ids)-eligible.keys())
        if invalid: raise ValueError(f'IDs outside the MEP/structure pilot scope: {invalid[:10]}.')
        eligible={i:eligible[i] for i in sorted(set(element_ids))}
    if len(eligible)>MAX_ELEMENTS:
        raise ValueError(f'Stage 3 pilot supports at most {MAX_ELEMENTS} eligible elements. Supply a subset of STEP IDs or load the small hard-clash sample. Whole-model tessellation was not started.')
    started=perf_counter()
    settings=ifcopenshell.geom.settings(); settings.set('use-world-coords',True)
    settings.set('context-identifiers',['Body'])
    bodies,skipped={},[]
    triangles=0
    for eid,element in sorted(eligible.items()):
        try:
            if not any(rep.RepresentationIdentifier=='Body' for rep in getattr(element.Representation,'Representations',())):
                raise ValueError('No Body representation supplied.')
            shape=ifcopenshell.geom.create_shape(settings,element)
            # Copy arrays while the owning shape is alive.
            vertices=np.array(shape.geometry.verts,dtype=np.float64).reshape(-1,3)
            faces=np.array(shape.geometry.faces,dtype=np.int64).reshape(-1,3)
            triangles+=len(faces)
            if triangles>MAX_TRIANGLES: raise ValueError('Stage 3 triangle limit exceeded; scan not evaluated.')
            bodies[eid]=make_body(vertices,faces)
        except Exception as exc:
            if triangles>MAX_TRIANGLES: raise ValueError(str(exc)) from exc
            skipped.append({'element_id':eid,'class':element.is_a(),'reason':str(exc)[:400]})
    mep=[i for i in bodies if eligible[i].is_a('IfcDistributionElement')]
    structure=[i for i in bodies if not eligible[i].is_a('IfcDistributionElement')]
    issues,unresolved,measurements=[],[],[]
    rejected,broad=0,0
    for aid in mep:
        for bid in structure:
            a,b=bodies[aid],bodies[bid]
            # Bounds exclude distant pairs only; retained pairs require booleans.
            if np.any(a.upper<b.lower) or np.any(b.upper<a.lower):
                rejected+=1; continue
            broad+=1
            if broad>MAX_PAIRS: raise ValueError('Stage 3 pair limit exceeded; scan not evaluated.')
            first,second=eligible[aid],eligible[bid]
            try:
                measurement={'element_ids':[aid,bid],'name':first.Name,**intersect_bodies(a,b)}
            except Exception as exc:
                measurement={'element_ids':[aid,bid],'name':first.Name,'intersection_status':'not_evaluated',
                             'depth_status':'not_evaluated','reason':str(exc)[:400]}
            depth=measurement.get('minimum_translation_mm')
            measurement['threshold_status']='not_applicable'
            if measurement['intersection_status']!='no_positive_volume_intersection':
                if measurement.get('depth_status')!='evaluated_convex_sat':
                    measurement['threshold_status']='not_evaluated'
                    unresolved.append(measurement)
                    issues.append(_pair_issue('hard_clash_depth_unresolved','info','Intersection needs depth review',
                        f"#{aid} versus #{bid}: {measurement['intersection_status'].replace('_',' ')}. Configured {tolerance_mm:g} mm threshold is Not evaluated; do not classify the pair as clear.",
                        first,second,selection_ids=[aid,bid],review_status='unresolved',measurement=measurement))
                elif depth<=tolerance_mm+NUMERIC_SLACK_MM:
                    measurement['threshold_status']='below_or_at_threshold'
                else:
                    measurement['threshold_status']='exceeds_threshold'
                    issues.append(_pair_issue('hard_clash','warning','Hard-clash candidate',
                        f"#{aid} versus #{bid}: solid intersection {measurement['intersection_volume_m3']:.6g} m³; convex minimum translation {depth:.3f} mm exceeds {tolerance_mm:g} mm. Review coordination intent.",
                        first,second,selection_ids=[aid,bid],minimum_translation_mm=depth,
                        intersection_volume_m3=measurement['intersection_volume_m3'],tolerance_mm=tolerance_mm,
                        measurement=measurement,review_status='unresolved',detection_basis='Manifold solid Boolean plus convex-polyhedron SAT; AABB used only for broad phase'))
            measurements.append(measurement)
    groups=bool(mep and structure)
    return {'stage':3,'app_version':APP_VERSION,'engine':'ifcopenshell+manifold3d','engine_version':ifcopenshell.version,
        'solid_engine_version':version('manifold3d'),'schema':model.schema,'generated_at':datetime.now(timezone.utc).isoformat(),
        'scope':'MEP versus structure' if element_ids is None else 'Selected IDs; MEP versus structure only',
        'selected_element_ids':sorted(eligible),'source_scope':'whole eligible model' if element_ids is None else 'explicit subset only',
        'tolerance_mm':tolerance_mm,'threshold_metric':'convex minimum translation to boundary contact',
        'numeric_slack_mm':NUMERIC_SLACK_MM,'volume_epsilon_m3':VOLUME_EPS_M3,
        'settings':{'use_world_coords':True,'context_identifiers':['Body'],'disable_opening_subtractions':False,'mesh_precision':'float64','mesh_repair':False},
        'extraction_complete_for_selected_scope':groups and not skipped,
        'complete_for_selected_scope':groups and not skipped and not unresolved,
        'detection_completeness_status':'selected tessellated-body scope only; not project certification',
        'scope_status':'evaluated' if groups else 'not_evaluated_missing_group',
        'summary':{'eligible_elements':len(eligible),'measured_elements':len(bodies),'mep_elements':len(mep),'structural_elements':len(structure),
            'candidate_pairs':sum(i['rule_id']=='hard_clash' for i in issues),'skipped_elements':len(skipped),'unresolved_collisions':len(unresolved),
            'triangles':triangles,'potential_pairs':len(mep)*len(structure),'broad_phase_pairs':broad,'broad_phase_rejected':rejected},
        'issues':issues,'skipped_elements':skipped,'unresolved_collisions':unresolved,'pair_measurements':measurements,
        'duration_ms':round((perf_counter()-started)*1000,1),
        'rule_source':'Manifold mesh Boolean; convex separating-axis theorem. Application threshold, not an industry acceptance limit.',
        'claim_boundary':'Bounded MEP/structure pilot on extracted tessellated bodies. Convex minimum translation differs from old kernel protrusion/pierce distance; containment values may change. Non-convex or over-limit positive intersections have depth Not evaluated and remain unresolved. Missing/rejected geometry prevents complete scope status. No clearance, self-clash, project approval, exact curved-CAD equivalence or author-intent verdict. Zero candidates does not prove a clash-free project.'}

def run_hard_clashes_file(path,tolerance_mm=2.,element_ids=None,source_sha256=None):
    import ifcopenshell
    path=Path(path)
    result=run_hard_clash_model(ifcopenshell.open(str(path)),tolerance_mm,element_ids)
    result['source_sha256']=source_sha256 or sha256(path.read_bytes()).hexdigest()
    return result

def run_hard_clashes_text(content,tolerance_mm=2.,element_ids=None):
    import ifcopenshell
    result=run_hard_clash_model(ifcopenshell.file.from_string(content),tolerance_mm,element_ids)
    result['source_sha256']=sha256(content.encode()).hexdigest()
    return result
