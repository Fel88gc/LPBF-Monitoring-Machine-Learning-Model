import json,hashlib
from pathlib import Path
from pypdf import PdfReader
from PIL import Image,ImageChops
base=Path(r'C:/Users/Felix/Documents/Codex/2026-11-08/can')
work=base/'work/data_cleaning_report_expanded_2026-11-15'
final=base/'outputs/FYP_Data_and_Cleaning_Update_2026-11-15.pdf'
old=PdfReader(work/'before_date_footer_removal.pdf')
new=PdfReader(final)
assert len(old.pages)==len(new.pages)==6
old_footer='FYP data preparation update - Felix - 15 November 2026'
new_footer='FYP data preparation update - Felix'
checks=[]
for i,(before,after) in enumerate(zip(old.pages,new.pages),1):
    before_text=before.extract_text()
    after_text=after.extract_text()
    assert before_text.replace(old_footer,new_footer)==after_text,i
    assert old_footer not in after_text,i
    with Image.open(work/f'page-{i}.png') as a,Image.open(work/f'clean-page-{i}.png') as b:
        assert a.size==b.size
        crop=(0,0,a.width,a.height-100)
        unchanged=ImageChops.difference(a.crop(crop),b.crop(crop)).getbbox() is None
        assert unchanged,i
    checks.append({'page':i,'only_footer_text_changed':True,'body_render_identical':unchanged})
record={'pages':6,'sha256':hashlib.sha256(final.read_bytes()).hexdigest(),'checks':checks}
(work/'footer_edit_verification.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record))
