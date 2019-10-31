# dyson
A repo of tools that can be used to clean up your raster data that stored in the cloud

## Tools
- **compare bundles to services** - generates a list of bundles and whether they have a corresponding image service
  - Connect to portal
  - List *Hosted* image services
  - Can we get S3 path for services using ArcGIS Python API or REST API?
  - Do we need boto\S3 credentials or can we go through Python API?
  - What do we need to do this?
    - Portal Admin account.
    - Credentials to raster datastore.
- **clean bucket** - deletes crfs in cloud storage that don't have a corresponding service in the portal.
  - **DONT IMPLEMENT DELETE YET**
- **fix service** - Build pyramids and statistics on a service that failed to generate pyramids and statistics.
- **fix bundle url** - fixes a broken link to a crf bundle in cloud storage.
