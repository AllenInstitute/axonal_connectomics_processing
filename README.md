# Axonal Connectomics Processing
This repo serves to build and integrate software used for axonal connectomics

## Individual packages
Constituent packages are independently installable and integrated using git submodules, referenced in this table:
| Module name | Repo | Description |
| :--- | :--- | :---: |
| acpreprocessing | [axonal_connectomics](https://github.com/AllenInstitute/axonal_connectomics) | image data preprocessing |
| ac_seg | [ac_segmentation](https://github.com/AllenInstitute/ac_segmentation) | voxel training and segmentation with skeletonization postprocessing |
| acanalysis | [ac_reconstruction_analysis](https://github.com/AllenInstitute/ac_reconstruction_analysis) | skeletonized reconstruction analysis and skeleton-base alignment |
| ac_pcg | [ac_pcg](https://github.com/AllenInstitute/ac_pcg) | chunkedgraph ingest and supervoxel generation for sparse skeleton + voxelization |

## Level of Support
We are planning on occasional updating this tool with no fixed schedule. Community involvement is encouraged through both issues and pull requests. Please make pull requests against the develop branch, as we will test changes there before merging into main.
