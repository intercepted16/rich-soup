// Helper function to extract spans with style information
function extractSpans(element) {
    const spans = [];
    const walker = document.createTreeWalker(
        element,
        NodeFilter.SHOW_TEXT,
        null,
        false
    );

    let node;
    while (node = walker.nextNode()) {
        const text = node.textContent.trim();
        if (!text) continue;

        const parent = node.parentElement;
        const style = getComputedStyle(parent);
        const fontWeight = parseFloat(style.fontWeight);
        const fontSize = parseFloat(style.fontSize);
        const fontFamily = style.fontFamily;

        // Check for bold/italic in parent element or its ancestors
        let bold = fontWeight >= 700;
        let italic = style.fontStyle === 'italic';
        let code = false;

        // Walk up to check for strong, b, em, i, code tags
        let ancestor = parent;
        while (ancestor && ancestor !== element) {
            const tag = ancestor.tagName?.toUpperCase() || '';
            if (tag === 'STRONG' || tag === 'B') bold = true;
            if (tag === 'EM' || tag === 'I') italic = true;
            if (tag === 'CODE' || tag === 'KBD' || tag === 'SAMP') code = true;
            ancestor = ancestor.parentElement;
        }

        spans.push({
            text: text,
            formats: (() => {
                const fmts = new Set();
                if (bold) fmts.add("bold");
                if (italic) fmts.add("italic");
                if (code) fmts.add("code");
                return fmts;
            })(),
            font_size: fontSize,
            font_weight: fontWeight,
            font_family: fontFamily
        });
    }

    return spans;
}


function extractTextNodes(selectors) {
    const SKIP_TAGS = new Set([
        'SCRIPT','STYLE','NOSCRIPT','IFRAME','SVG','CANVAS',
        'VIDEO','AUDIO','OBJECT','EMBED','META','LINK',
        'BUTTON','INPUT','SELECT','TEXTAREA','LABEL',
        'NAV','FOOTER','ASIDE','MENU','MENUITEM',
        'FORM','FIELDSET','OPTION','DATALIST',
        'DIALOG','SUMMARY','TEMPLATE','SLOT',
        'IMG','PICTURE','SOURCE','TRACK',
        'PROGRESS','METER','OUTPUT'
    ]);

    const NAV_ROLES = new Set([
        'navigation','banner','contentinfo','complementary',
        'search','form','menu','menubar','toolbar',
        'tab','tablist','tabpanel','dialog','alertdialog',
        'status','log','marquee','timer','tooltip'
    ]);

    const TABLE_TAGS = new Set(['TABLE','THEAD','TBODY','TFOOT','TR','TD','TH','CAPTION','COL','COLGROUP']);
    const HEADING_TAGS = {'H1':1,'H2':2,'H3':3,'H4':4,'H5':5,'H6':6};



    const elements = document.querySelectorAll(selectors.join(','));
    const blocks = [];
    const extractedTexts = [];

    elements.forEach(el => {
        const tagName = el.tagName?.toUpperCase() || '';
        const role = el.getAttribute('role')?.toLowerCase() || '';
        const ariaHidden = el.getAttribute('aria-hidden') === 'true';

        // Skip element or ancestors with skip tags/roles
        let ancestor = el, hasSkipAncestor=false, hasTableAncestor=false;
        while(ancestor && ancestor !== document.body){
            const ancestorTag = ancestor.tagName?.toUpperCase() || '';
            const ancestorRole = ancestor.getAttribute?.('role')?.toLowerCase() || '';
            if(SKIP_TAGS.has(ancestorTag) || NAV_ROLES.has(ancestorRole)){ hasSkipAncestor=true; break; }
            if(TABLE_TAGS.has(ancestorTag)) hasTableAncestor=true;
            ancestor = ancestor.parentElement;
        }
        if(hasSkipAncestor) return;

        const style = getComputedStyle(el);
        if(style.display==='none'||style.visibility==='hidden'||style.opacity==='0'||ariaHidden) return;

        const text = el.innerText?.trim();
        if(!text) return;

        const wordCount = text.split(/\s+/).length;
        const isTableCell = TABLE_TAGS.has(tagName);

        if((isTableCell || hasTableAncestor) && wordCount<20) return;
        if(wordCount<4 && !HEADING_TAGS[tagName]) return;

        const bbox = el.getBoundingClientRect();
        if(bbox.width<=0 || bbox.height<=0) return;

        const fontSize = parseFloat(style.fontSize);
        const fontWeight = parseFloat(style.fontWeight);
        const fontFamily = style.fontFamily;
        const headingLevel = HEADING_TAGS[tagName] || 0;

        // Duplicate check: children vs parent
        const childrenTextLength = Array.from(el.children).reduce((acc, child) => acc + (child.innerText?.trim()?.length || 0), 0);
        if(childrenTextLength > 0 && text.length > 0 && (childrenTextLength / text.length) > 0.85) return;

        // Check against previously extracted texts (same logic as Python)
        let isDuplicate = false;
        const textsToRemove = [];
        extractedTexts.forEach((existing, idx)=>{
            if(existing.includes(text)){
                isDuplicate = true;
            } else if(text.includes(existing)){
                textsToRemove.push(idx);
            }
        });
        if(isDuplicate) return;
        textsToRemove.reverse().forEach(idx=>{
            extractedTexts.splice(idx,1);
            blocks.splice(idx,1);
        });

        // Skip list items - they're handled by extractLists()
        if(['LI','DT','DD','UL','OL'].includes(tagName)){
            return;
        }

        // Extract spans for regular text block
        const spans = extractSpans(el);

        // Regular text block
        blocks.push({
            type:'text',
            text:text,
            spans:spans,
            bbox:{x:bbox.x,y:bbox.y,width:bbox.width,height:bbox.height},
            fontSize,fontWeight,fontFamily,headingLevel
        });
        extractedTexts.push(text);
    });

    return blocks;
}


function extractLists() {
    const blocks = [];
    const lists = document.querySelectorAll("ul, ol");

    for (const list of lists) {
        const listItems = Array.from(list.querySelectorAll(":scope > li"));
        if (listItems.length === 0) continue;

        const items = [];
        for (const li of listItems) {
            const spans = extractSpans(li);
            if (spans.length > 0) {
                items.push(spans);
            }
        }

        if (items.length === 0) continue;

        const bbox = list.getBoundingClientRect();
        if (bbox.width <= 0 || bbox.height <= 0) continue;

        const ordered = list.tagName === "OL";

        blocks.push({
            type: "list",
            items: items,
            ordered: ordered,
            level: 0,
            bbox: {
                x: bbox.x,
                y: bbox.y,
                width: bbox.width,
                height: bbox.height
            }
        });
    }

    return blocks;
}


function extractImages() {
    const blocks = [];

    const images = document.images;

    for (const img of images) {
        if (img.offsetHeight === 0 || img.offsetWidth === 0) continue;
        if (!img.src) continue;
        
        const bbox = img.getBoundingClientRect();
        if(bbox.width<=0 || bbox.height<=0) continue;
        blocks.push({
            type:'image',
            src:img.src,
            bbox:{x:bbox.x,y:bbox.y,width:bbox.width,height:bbox.height},
            alt: img.getAttribute('alt') || null
        });
    }
    
    return blocks;

}

function extractTables() {
    const blocks = [];

    const tables = document.querySelectorAll("table");
    tables.forEach(table => {
        const rows = Array.from(table.querySelectorAll("tr"));
        const rows_data = [];

        rows.forEach(tr => {
            const cells = Array.from(tr.querySelectorAll("td, th"));
            // Keep empty cells to maintain column alignment
            const row_texts = cells.map(cell => cell.innerText.trim() || "");
            if(row_texts.length > 0) {
                rows_data.push(row_texts);
            }
        });

        if(rows_data.length === 0) return;

        const bbox = table.getBoundingClientRect();
        if(bbox.width <= 0 || bbox.height <= 0) return;

        blocks.push({
            type: "table",
            rows: rows_data,
            bbox: {
                x: bbox.x,
                y: bbox.y,
                width: bbox.width,
                height: bbox.height
            }
        });
    });

    return blocks;
}

function extractLinks() {
    const blocks = [];
    const links = document.querySelectorAll("a[href]");

    for (const link of links) {
        const href = link.getAttribute("href");
        
        // Only extract links starting with https://
        if (!href || !href.startsWith("https://")) continue;
        
        const text = link.innerText?.trim();
        if (!text) continue;
        
        const bbox = link.getBoundingClientRect();
        if (bbox.width <= 0 || bbox.height <= 0) continue;
        
        const spans = extractSpans(link);
        
        blocks.push({
            type: "link",
            href: href,
            spans: spans,
            bbox: {
                x: bbox.x,
                y: bbox.y,
                width: bbox.width,
                height: bbox.height
            }
        });
    }

    return blocks;
}
