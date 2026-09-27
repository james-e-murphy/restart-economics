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
  -- page foot; a section's figures are placed before the next section begins
  if el.level == 1 then
    return {pandoc.RawBlock('latex', '\\FloatBarrier\\Needspace{7\\baselineskip}'), el}
  end
  if el.level == 2 then
    return {pandoc.RawBlock('latex', '\\Needspace{7\\baselineskip}'), el}
  end
end

-- A table nested inside another block, which the Blocks pass above does not float: one short
-- enough to fit on a page starts on a new page rather than splitting a few rows off onto the
-- next; a long one breaks where it must.
function Table(el)
  local n = 0
  for _, b in ipairs(el.bodies) do n = n + #b.body end
  if n <= 40 then
    local lines = math.floor(n * 1.6 + 12)
    return {pandoc.RawBlock('latex', '\\Needspace{' .. lines .. '\\baselineskip}'), el}
  end
end


-- Every table is set as a tabular inside a table float rather than as a longtable, so that a
-- full-page table goes onto the next page that can hold it while the text flows on, and a
-- shorter one sits where it fits; a longtable cannot float. Cells are written by the LaTeX
-- writer itself, so emphasis and special characters come out as they would anywhere. Modes:
-- 'natural' (a ::: nowrap ::: div) sets every column at its natural width so that no cell
-- wraps, in the smaller face; 'small' (a ::: small ::: div) keeps the pipe table's proportional
-- widths in the smaller face; 'normal' is every other table, proportional widths in the body
-- table face.
local function tex(blocks)
  return (pandoc.write(pandoc.Pandoc(blocks), 'latex'):gsub('%s+$', ''))
end

-- the most rows a float can hold on one page in each mode; a longer table stays a longtable,
-- which breaks across pages where it must
local FLOAT_ROWS = { natural = 46, small = 30, normal = 24 }

local function float_table(tbl, mode)
  local n = 0
  for _, b in ipairs(tbl.bodies) do n = n + #b.body end
  if n > FLOAT_ROWS[mode] then return nil end
  local cols = {}
  for i, spec in ipairs(tbl.colspecs) do
    local a, w = spec[1], spec[2]
    local align = (a == 'AlignRight') and 'r' or (a == 'AlignCenter') and 'c' or 'l'
    if mode == 'natural' or type(w) ~= 'number' then
      cols[i] = align
    else
      local rag = (align == 'r') and '\\raggedleft' or (align == 'c') and '\\centering'
                  or '\\raggedright'
      cols[i] = '>{' .. rag .. '\\arraybackslash}p{\\dimexpr' .. string.format('%.4f', w)
                .. '\\textwidth-2\\tabcolsep\\relax}'
    end
  end
  local function row(r)
    local cells = {}
    for i, c in ipairs(r.cells) do cells[i] = tex(c.contents) end
    return table.concat(cells, ' & ') .. ' \\\\'
  end
  local lines = {}
  for _, r in ipairs(tbl.head.rows) do table.insert(lines, row(r)) end
  table.insert(lines, '\\midrule')
  for _, b in ipairs(tbl.bodies) do
    for _, r in ipairs(b.body) do table.insert(lines, row(r)) end
  end
  local caption = tex(tbl.caption.long)
  local where = n > 30 and '[p]' or '[!htbp]'
  local look = (mode == 'natural') and '\\setlength{\\tabcolsep}{3.5pt}\\setlength{\\extrarowheight}{0.4pt}\\renewcommand{\\arraystretch}{1.02}'
            or (mode == 'small') and '\\setlength{\\tabcolsep}{3.5pt}\\setlength{\\extrarowheight}{1pt}\\renewcommand{\\arraystretch}{1.15}'
            or '\\setlength{\\tabcolsep}{\\LTsep}\\setlength{\\extrarowheight}{\\LTextra}\\renewcommand{\\arraystretch}{\\LTstretch}'
  return pandoc.RawBlock('latex',
    '\\begin{table}' .. where .. '\n\\caption{' .. caption .. '}\n\\centering\\LTfont' .. look .. '\n'
    .. '\\begin{tabular}{' .. table.concat(cols) .. '}\n\\toprule\n'
    .. table.concat(lines, '\n') .. '\n\\bottomrule\n\\end{tabular}\n\\end{table}')
end


-- A fenced ::: box ::: div is set as a framed callout.
function Div(el)
  -- A ::: nowrap ::: div sets its tables at their natural column widths, so that no cell
  -- wraps, with a narrower column gap; assemble.py uses it for the ladder table.
  -- a table too long to float stays a longtable; in a nowrap or small div it keeps the smaller
  -- face and the narrower gap
  if el.classes:includes('nowrap') or el.classes:includes('small') then
    local out = {pandoc.RawBlock('latex',
      '\\begingroup\\renewcommand{\\LTfont}{\\footnotesize}\\setlength{\\LTsep}{3.5pt}'
      .. '\\setlength{\\LTextra}{1pt}\\renewcommand{\\LTstretch}{1.15}')}
    for _, b in ipairs(el.content) do table.insert(out, b) end
    table.insert(out, pandoc.RawBlock('latex', '\\endgroup'))
    return out
  end
  if el.classes:includes('box') then
    local out = {pandoc.RawBlock('latex','\\begin{examplebox}')}
    for _,b in ipairs(el.content) do table.insert(out, b) end
    table.insert(out, pandoc.RawBlock('latex','\\end{examplebox}'))
    return out
  end
end


-- A figure and the caption that follows it are kept together as one float: without this a
-- caption can be split from its figure, or across a page break. Set as a float rather than an
-- in-line minipage, a figure that does not fit the rest of its page goes to the top of the next
-- and the text flows on, instead of leaving the rest of the page blank. Floats of one kind keep
-- their order, so figures stay numbered in sequence. This runs as a pass of its own, before the
-- passes above turn the image and the caption into raw LaTeX.
local function keep_figures(blocks)
  local out = {}
  local i = 1
  while i <= #blocks do
    local b, nxt = blocks[i], blocks[i + 1]
    if b.t == 'Div' and (b.classes:includes('nowrap') or b.classes:includes('small')) then
      local tbl
      pandoc.walk_block(b, { Table = function(t) tbl = t; return t end })
      local made = tbl and float_table(tbl, b.classes:includes('nowrap') and 'natural' or 'small')
      if made then
        table.insert(out, made)
      else
        -- a table too long to float is set where it stands, after any float still waiting,
        -- so that the tables keep their order
        table.insert(out, pandoc.RawBlock('latex', '\\FloatBarrier'))
        table.insert(out, b)
      end
      i = i + 1
    elseif b.t == 'Table' then
      local made = float_table(b, 'normal')
      if made then
        table.insert(out, made)
      else
        table.insert(out, pandoc.RawBlock('latex', '\\FloatBarrier'))
        table.insert(out, b)
      end
      i = i + 1
    elseif b.t == 'Header' and b.level == 1 and nxt and nxt.t == 'Header' and nxt.level == 2 then
      -- a section heading directly over a subsection heading: room for both and a few lines
      table.insert(out, pandoc.RawBlock('latex', '\\Needspace{13\\baselineskip}'))
      table.insert(out, b)
      i = i + 1
    elseif b.t == 'Para' and #b.content == 1 and b.content[1].t == 'Image' and nxt
       and nxt.t == 'BlockQuote' and pandoc.utils.stringify(nxt):match('^Figure %u?%d') then
      table.insert(out, pandoc.RawBlock('latex', '\\begin{figure}[!htbp]'))
      table.insert(out, b)
      table.insert(out, nxt)
      table.insert(out, pandoc.RawBlock('latex', '\\end{figure}'))
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
