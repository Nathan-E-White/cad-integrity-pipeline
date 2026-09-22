# Geometry inspection

Domain language for inspecting polygonal and native geometry and diagnostic results.

## Language

**Polygonal face**:
A face belonging to a particular polygonal mesh revision, identified independently
of its display triangulation. It is the face-level inspection entity, including
when its interior cannot be rendered.
_Avoid_: Render triangle as a synonym for polygonal face.

**Display triangle**:
A triangle representing part or all of one **polygonal face** or **native face**
for visualization. A face may have multiple display triangles or none when its
interior cannot be rendered. The source domain is explicit; native faces do not
become polygonal cells through display tessellation.
_Avoid_: Source face as a synonym for an individual display triangle.

**Native face**:
An OCCT face occurrence in a particular retained native shape snapshot. Its local
ordinal follows that snapshot's indexed face map. Copy history associates display
faces with this source map; ordinals alone do not establish correspondence between
original and candidate shapes or between revisions.

**Display projection**:
An owned set of display geometry and source-face correspondence. Its identity
scopes display triangle ordinals; a new tessellation cannot reuse old triangle
references merely because the native shape is unchanged.

## Example dialogue

Developer: “The pointer hit one of the three display triangles. Which face is selected?”

Domain expert: “Their polygonal face. The three triangles represent one inspection entity.”
