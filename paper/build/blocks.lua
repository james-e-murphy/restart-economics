local function raw(s) return pandoc.RawBlock('latex', s) end

function BlockQuote(el)
  local txt = pandoc.utils.stringify(el)
  local out = {}
  if txt:match("^Figure %u?%d") then
    table.insert(out, raw('\\par\\addvspace{4pt}\\begin{figcaption}'))
    for _,b in ipairs(el.content) do table.insert(out, b) end
    table.insert(out, raw('\\end{figcaption}'))
    return out
  end
  local stripped = pandoc.walk_block(el, {
    Strong = function(s) return s.content end
  })
  -- re-bold a leading proposition identifier such as "P3."
  local first = stripped.content[1]
  if first and first.t == 'Para' then
    local ils = first.content
    if ils[1] and ils[1].t == 'Str' and ils[1].text:match('^P%d%.$') then
      ils[1] = pandoc.Strong({pandoc.Str(ils[1].text)})
    end
  end
  -- \par forces vertical mode and \addvspace restores the frame's skipabove,
  -- which mdframed loses when a framed block directly follows a section heading.
  table.insert(out, raw('\\par\\addvspace{10pt}\\begin{keystatement}'))
  for _,b in ipairs(stripped.content) do table.insert(out, b) end
  table.insert(out, raw('\\end{keystatement}'))
  return out
end

-- implicit_figures is disabled at the reader, so a lone image arrives as a Para.
-- Render it centred, sized to the text block, with no auto caption; the manuscript
-- supplies its own caption immediately below as a figcaption blockquote.
function Para(el)
  if #el.content == 1 and el.content[1].t == 'Image' then
    local src = el.content[1].src
    return pandoc.RawBlock('latex',
      '\\begin{center}\\vspace{2pt}\\includegraphics[width=\\textwidth,height=0.66\\textheight,keepaspectratio]{'
      .. src .. '}\\vspace{-2pt}\\end{center}')
  end
end

-- The markdown uses `---` as a section separator. Numbered headings already
-- provide that break in the typeset document, where the rules render as stray
-- centred lines, often orphaned at a page foot.
function HorizontalRule(el)
  return {}
end

-- The table of contents ends wherever it ends, so without this the Abstract
-- begins mid page directly under the last contents entry. Start the body on a
-- fresh page instead.
function Header(el)
  if el.level == 1 and pandoc.utils.stringify(el) == 'Abstract' then
    return {pandoc.RawBlock('latex', '\\clearpage'), el}
  end
  -- keep a heading with the first lines of what follows it rather than stranding it at a
  -- page foot
  if el.level <= 2 then
    return {pandoc.RawBlock('latex', '\\Needspace{7\\baselineskip}'), el}
  end
end

-- A table short enough to fit on a page starts on a new page rather than splitting a few rows
-- off onto the next; a long one breaks where it must.
function Table(el)
  local n = 0
  for _, b in ipairs(el.bodies) do n = n + #b.body end
  if n <= 24 then
    local lines = math.floor(n * 1.8 + 10)
    return {pandoc.RawBlock('latex', '\\Needspace{' .. lines .. '\\baselineskip}'), el}
  end
end


-- A fenced ::: box ::: div is set as a framed callout, used for the stylized
-- example in 5.8. Previously the manuscript described a box that was never drawn.
function Div(el)
  if el.classes:includes('box') then
    local out = {pandoc.RawBlock('latex','\\begin{examplebox}')}
    for _,b in ipairs(el.content) do table.insert(out, b) end
    table.insert(out, pandoc.RawBlock('latex','\\end{examplebox}'))
    return out
  end
end


-- A figure and the caption that follows it are kept on one page: without this a caption can
-- be split from its figure, or across a page break. This runs as a pass of its own, before the
-- passes above turn the image and the caption into raw LaTeX.
local function keep_figures(blocks)
  local out = {}
  local i = 1
  while i <= #blocks do
    local b, nxt = blocks[i], blocks[i + 1]
    if b.t == 'Para' and #b.content == 1 and b.content[1].t == 'Image' and nxt
       and nxt.t == 'BlockQuote' and pandoc.utils.stringify(nxt):match('^Figure %u?%d') then
      table.insert(out, pandoc.RawBlock('latex',
        '\\par\\noindent\\begin{minipage}{\\textwidth}'))
      table.insert(out, b)
      table.insert(out, nxt)
      table.insert(out, pandoc.RawBlock('latex', '\\end{minipage}\\par\\medskip'))
      i = i + 2
    else
      table.insert(out, b)
      i = i + 1
    end
  end
  return out
end

return {
  {Blocks = keep_figures},
  {BlockQuote = BlockQuote, Para = Para, HorizontalRule = HorizontalRule, Header = Header,
   Table = Table, Div = Div},
}
