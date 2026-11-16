"""Preserve the current human priority and verified continuation evidence."""
import copy
import httpx
import huce_document_pipeline as p


def main():
    p.event('preflight',p.preflight())
    predecessor=p.BASE/'it-common-priority-20261022-66.json'
    priority=copy.deepcopy(p.read(predecessor))
    probes=p.BASE/'events/20261022T081122897069Z-retrieval-source-probes.json'
    assert p.read(probes)['passed'] and len(p.read(probes)['results'])==6
    ready=p.read(p.PUB/'reviewed-corrections-20261021-v27.ready.json')
    assert ready['index_sha256']==p.sha(p.checked(p.ROOT/ready['index']).read_bytes())
    verification=max((p.BASE/'events').glob('*-verification.json'))
    assert p.read(verification)['baseline_fingerprint']==ready['fingerprint']
    priority.update(at=p.now(),predecessor=p.rel(predecessor),
        reason='Direct human priority: all CNTT-related sources and common university/student documents first; other-major-specific sources deferred.',
        current_catalog=p.rel(p.CATALOG),current_catalog_sha256=p.sha(p.CATALOG.read_bytes()),
        conference_source_status='All32originalPDFimages and twoHTMLbodies read. Ready27:123new excerpts;909active parents,2503vectors,529history rows. Six unchanged realBGEqueries pass with stricter exact-section assertions. Source schedule/author variants remain unresolved; neitherPDFiscomplete.',
        conference_probe_receipt=p.rel(probes),full_verification_receipt=p.rel(verification),
        common_content_review=p.rel(p.BASE/'common-student-support-content-review-20261022-68.json'),
        common_annex_geometry=p.rel(p.BASE/'common-support-annex-geometry-20261022-69.json'),
        common_template_acquisition=p.rel(p.BASE/'common-application-template-acquisition-20261022-67.json'),
        common_status='All5unique originalPDFimages and full native text read;3annex tables independently extracted/read;2officialHTMLbodies/links/dates checked. ThreeDOCXform texts read with bundled Python. Template layout pending: LibreOffice missing. Notice338versus linkedform legal citation and LôLô/LôTô differences recorded, not silently repaired. Not normalized/indexed; pending identities not added to catalog.',
        next_priority='Normalize common notice338and annex with merged-cell inheritance and exclusions; keep2Driveidentities for identical5pagePDF. Bind both officialHTMLdates and source links. Resolve DOCX rendering inside authorizedworkspace, retain old form citations and explicit variants. Then continue common handbook, rules, fees and remaining CNTT source bodies. Other-major-specific documents deferred.')
    target=p.BASE/'it-common-priority-20261022-70.json';p.save(target,priority)
    health=httpx.get('http://127.0.0.1:8006/health/entry',trust_env=False,timeout=10);health.raise_for_status()
    p.event('runtime-verified',{'backend_pid':22704,'backend_session':41457,'health':health.json(),
        'loaded_release_on_startup':27,'startup_index_fingerprint':ready['fingerprint'],
        'fingerprint_basis':'Latest ready release at verified backend startup; health does not expose a fingerprint.',
        'model_service_restart':False,'paid_generation_calls':0,'budgets_changed':False,
        'tests':'27conference and hybrid regression tests passed; prior English7passed. Initial broader attempt failed Windows temp setup, then rerun in new retained workspace temp succeeded.'})
    print(p.rel(target));p.checkpoint(None)


if __name__=='__main__':main()
