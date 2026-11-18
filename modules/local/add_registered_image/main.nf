process ADD_REGISTERED_IMAGE {
    label "process_medium"
    tag "${meta.sample}"

    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container
?         'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/70/707825bb6afa202806406063665a361b2a4a2fc6d6f802132359407408826ffe/data'
:         'community.wave.seqera.io/library/python_sopa:54a97bc5a187152d' }"

    input:
    // The H&E and its run folder are in the tuple so they join to their own store by key.
    tuple val(meta), path(sdata_path), path(he_image), path(run_dir)

    output:
    // Mutates the store in place: adds {sample}_he and the he_registration attribute.
    tuple val(meta), path(sdata_path), emit: sdata
    path "versions.yml"              , emit: versions

    script:
    """
    add_registered_image.py \\
        --sdata ${sdata_path} \\
        --image ${he_image} \\
        --run ${run_dir} \\
        --element ${meta.sample}_he \\
        --published preprocessing/he_registration/${meta.id}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        spatialdata: \$(python -c "import spatialdata; print(spatialdata.__version__)" 2> /dev/null)
    END_VERSIONS
    """

    stub:
    """
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        spatialdata: stub
    END_VERSIONS
    """
}
