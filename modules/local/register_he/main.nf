// Register a same-section H&E onto Ashlar's stitched IF with valis_pipeline (VALIS 1.2.0).
// The image holds valis_pipeline's two environments; run.py runs every step of one config.
process REGISTER_HE {
    tag "${meta.id}"
    label 'process_high'

    container "docker.io/leventetn/valis_pipeline:1.0.0"

    input:
    // Staged apart: the H&E may share the stitched image's file name.
    tuple val(meta), path(ifimage, stageAs: 'if/*'), path(heimage, stageAs: 'he/*'), val(channel_index)

    output:
    tuple val(meta), path("${meta.id}")              , emit: run
    tuple val(meta), path("${meta.id}_he.ome.tif")   , emit: image
    path "versions.yml"                              , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    """
    # libvips and VALIS write large temporary files: keep them in the work directory.
    mkdir -p tmp
    export TMPDIR=\$PWD/tmp VIPS_CONCURRENCY=${task.cpus} SLURM_CPUS_PER_TASK=${task.cpus}

    he_registration_config.py \\
        --name ${meta.id} \\
        --if-image ${ifimage} \\
        --channel-index ${channel_index} \\
        --he-image ${heimage} \\
        ${args} \\
        > config.yml

    python /opt/valis_pipeline/scripts/run.py config.yml

    mv ${meta.id}/spatialdata/he_on_if.ome.tif ${meta.id}_he.ome.tif
    # VALIS' working folder and the converted or cropped inputs: tens of GB, not needed once the maps exist.
    rm -rf ${meta.id}/valis ${meta.id}/inputs/*.ome.tif tmp

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        valis-wsi: \$(python -c "import json; print(json.load(open('${meta.id}/registration.json'))['versions']['valis-wsi'])")
        valis_pipeline: \$(python -c "import json; print(json.load(open('${meta.id}/registration.json'))['code_version'])")
    END_VERSIONS
    """

    stub:
    """
    mkdir -p ${meta.id}/qc ${meta.id}/spatialdata ${meta.id}/maps
    echo '{}' > ${meta.id}/placement.json
    echo '{"state": "complete", "code_version": "stub", "versions": {"valis-wsi": "stub"}}' > ${meta.id}/registration.json
    echo '{"state": "complete", "map_stage": "micro", "mode": "none"}' > ${meta.id}/spatialdata/provenance.json
    echo 'source,tier,stage,direction,n,median_um,p90_um,within_5um_percent' > ${meta.id}/qc/summary.csv
    touch ${meta.id}_he.ome.tif

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        valis-wsi: stub
        valis_pipeline: stub
    END_VERSIONS
    """
}
