# Polygonal inspection

Domain language for inspecting polygonal geometry and its diagnostic results.

## Language

**Polygonal face**:
A face belonging to a particular polygonal mesh revision, identified independently
of its display triangulation. It is the face-level inspection entity, including
when its interior cannot be rendered.
_Avoid_: Render triangle as a synonym for polygonal face.

**Display triangle**:
A triangle representing part or all of one **polygonal face** for visualization.
A polygonal face may have multiple display triangles or none when its interior
cannot be rendered.
_Avoid_: Source face as a synonym for an individual display triangle.

## Example dialogue

Developer: “The pointer hit one of the three display triangles. Which face is selected?”

Domain expert: “Their polygonal face. The three triangles represent one inspection entity.”
