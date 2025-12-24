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

    let listAccumulator = [];
    let listBBox = null;
    let listFontSize = 0, listFontWeight = 0, listFontFamily = null, listHeadingLevel = 0;

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

        // Handle list items
        if(['LI','DT','DD'].includes(tagName)){
            const prefix = tagName==='LI'?'-':'*';
            listAccumulator.push(`${prefix} ${text}`);
            if(!listBBox){
                listBBox=bbox; listFontSize=fontSize; listFontWeight=fontWeight;
                listFontFamily=fontFamily; listHeadingLevel=headingLevel;
            } else {
                const x0 = Math.min(listBBox.x,bbox.x);
                const y0 = Math.min(listBBox.y,bbox.y);
                const x1 = Math.max(listBBox.x+listBBox.width,bbox.x+bbox.width);
                const y1 = Math.max(listBBox.y+listBBox.height,bbox.y+bbox.height);
                listBBox={x:x0,y:y0,width:x1-x0,height:y1-y0};
            }
            return;
        }

        // Flush accumulated list if any
        if(listAccumulator.length && listBBox){
            blocks.push({
                type:'text',
                text:listAccumulator.join('\n'),
                bbox:{x:listBBox.x,y:listBBox.y,width:listBBox.width,height:listBBox.height},
                fontSize:listFontSize,fontWeight:listFontWeight,fontFamily:listFontFamily,
                headingLevel:listHeadingLevel
            });
            listAccumulator=[]; listBBox=null;
        }

        // Regular text block
        blocks.push({
            type:'text',
            text:text,
            bbox:{x:bbox.x,y:bbox.y,width:bbox.width,height:bbox.height},
            fontSize,fontWeight,fontFamily,headingLevel
        });
        extractedTexts.push(text);
    });

    // Flush any remaining list
    if(listAccumulator.length && listBBox){
        blocks.push({
            type:'text',
            text:listAccumulator.join('\n'),
            bbox:{x:listBBox.x,y:listBBox.y,width:listBBox.width,height:listBBox.height},
            fontSize:listFontSize,fontWeight:listFontWeight,fontFamily:listFontFamily,
            headingLevel:listHeadingLevel
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
            bbox:{x:bbox.x,y:bbox.y,width:bbox.width,height:bbox.height}
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
            const row_texts = cells.map(cell => cell.innerText.trim()).filter(text => text.length > 0);
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
