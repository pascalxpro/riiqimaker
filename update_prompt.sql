UPDATE prompt_templates
SET body = '{theme}. {style} style. Main text: "{text}".
Flat lay surface pattern design, top-down view. Illustrated repeating pattern.
Flat 2D vector illustration, pure white background, vibrant colors, seamless left-right edges.
No 3D, no cup shape, no border frame, no shadows, no perspective.'
WHERE id = (SELECT id FROM prompt_templates ORDER BY id LIMIT 1);
