'''
Classes for carving and fusion of images into voxel grids.
Typically will be given a voxel grid and an RGBD 'video', and will do the
fusion/carving
'''
import numpy as np
import voxel_data
from copy import deepcopy

from skimage.restoration import denoise_bilateral

# temp = denoise_bilateral(vid.frames[0].depth)
import scipy.ndimage
import scipy.interpolate


class VoxelAccumulator(object):
    '''
    base class for kinect fusion and voxel carving
    '''

    def __init__(self):
        pass

    def set_video(self, video_in):
        self.video = video_in

    def set_voxel_grid(self, voxel_grid):
        self.voxel_grid = voxel_grid

    def project_voxels(self, im):
        '''
        projects the voxels into the specified camera.
        returns tuple of:
            a) A binary array of which voxels project into the image
            b) For each voxel that does, its uv position in the image
        '''

        # Projecting voxels into image
        xyz = self.voxel_grid.world_meshgrid()
        projected_voxels = im.cam.project_points(xyz)

        # seeing which are inside the image or not
        uv = np.round(projected_voxels[:, :2]).astype(int)
        inside_image = np.logical_and.reduce((uv[:, 0] >= 0,
                                              uv[:, 1] >= 0,
                                              uv[:, 1] < im.depth.shape[0],
                                              uv[:, 0] < im.depth.shape[1]))
        uv = uv[inside_image, :]
        depths = projected_voxels[inside_image, 2]
        return (inside_image, uv, depths)


class Carver(VoxelAccumulator):
    '''
    class for voxel carving
    Possible todos:
    - Allow for only a subset of frames to be used
    - Allow for use of TSDF
    '''
    def carve(self, tsdf=False):
        '''
        for each camera, project voxel grid into camera
        and see which ahead/behind of depth image.
        Use this to carve out empty voxels from grid
        'tsdf' being true means that the kinect-fusion esque approach is taken,
        where the voxel grid is populated with a tsdf
        '''
        vox = self.voxel_grid

        for count, im in enumerate(self.video.frames):

            # print "\nFrame number %d with name %s" % (count, im.frame_id)

            # now work out which voxels are in front of or behind the depth
            # image and location in camera image of each voxel
            inside_image, uv, depth_to_voxels = self.project_voxels(im)
            all_observed_depths = depth[uv[:, 1], uv[:, 0]]

            print "%f%% of voxels projected into image" % \
                (float(np.sum(inside_image)) / float(inside_image.shape[0]))

            # doing the voxel carving
            known_empty_s = all_observed_depths > depth_to_voxels
            known_empty_f = np.zeros(vox.V.flatten().shape, dtype=bool)
            known_empty_f[inside_image] = known_empty_s

            existing_values = vox.get_indicated_voxels(known_empty_f)
            vox.set_indicated_voxels(known_empty_f, existing_values + 1)

            print "%f%% of voxels seen to be empty" % \
                (float(np.sum(known_empty_s)) / float(known_empty_s.shape[0]))

        return self.voxel_grid


class KinfuAccumulator(voxel_data.WorldVoxels):
    '''
    An accumulator which can be used for kinect fusion etc
    valid_voxels are voxels which have been observed as empty or lie in the
    narrow band around the surface.
    '''
    def __init__(self, gridsize, dtype=np.float16):
        self.gridsize = gridsize
        self.weights = np.zeros(gridsize, dtype=dtype)
        self.tsdf = np.zeros(gridsize, dtype=dtype)
        self.valid_voxels = np.zeros(gridsize, dtype=bool)

    def update(self, valid_voxels, weight_values, tsdf_values):
        '''
        updates both the weights and the tsdf with a new set of values
        '''
        assert(np.sum(valid_voxels) == weight_values.shape[0])
        assert(np.sum(valid_voxels) == tsdf_values.shape[0])
        assert(np.prod(valid_voxels.shape) == np.prod(self.gridsize))

        # update the weights (no temporal smoothing...)
        valid_voxels = valid_voxels.reshape(self.gridsize)
        new_weights = self.weights[valid_voxels] + weight_values

        # tsdf update is more complex. We can only update the values of the
        # 'valid voxels' as determined by inputs
        valid_weights = self.weights[valid_voxels]
        valid_tsdf = self.tsdf[valid_voxels]

        numerator1 = (valid_weights * valid_tsdf)
        numerator2 = (weight_values * tsdf_values)
        self.tsdf[valid_voxels] = (numerator1 + numerator2) / (new_weights)

        # assign the updated weights
        self.weights[valid_voxels] = new_weights

        # update the valid voxels matrix
        self.valid_voxels[valid_voxels] = True

    def get_current_tsdf(self):
        '''
        returns the current state of the tsdf
        '''
        temp = self.copy()
        temp.weights = []
        temp.tsdf = []
        temp.valid_voxels = []
        temp.V = self.tsdf
        temp.V[self.valid_voxels == False] = np.nan
        return temp


class Fusion(VoxelAccumulator):
    '''
    Fuses images with known camera poses into one tsdf volume
    Largely uses kinect fusion algorithm (ismar2011), with some changes and
    simplifications.
    Note that even ismar2011 do not use bilateral filtering in the fusion
    stage, see just before section 3.4.
    Uses a 'weights' matrix to keep a rolling average (see ismar2011 eqn 11)
    '''
    def truncate(self, x, truncation):
        '''
        truncates values in array x to +/i mu
        '''
        x[x > truncation] = truncation
        x[x < -truncation] = -truncation
        return x

    def _fill_in_nans(self, depth):
        # a boolean array of (width, height) which False where there are
        # missing values and True where there are valid (non-missing) values
        mask = ~np.isnan(depth)

        # location of valid values
        xym = np.where(mask)

        # location of missing values
        xymis = np.where(~mask)

        # the valid values of the input image
        data0 = np.ravel( depth[mask] )

        # three separate interpolators for the separate color channels
        interp0 = scipy.interpolate.NearestNDInterpolator( xym, data0 )

        # interpolate the whole image, one color channel at a time
        guesses = interp0(xymis) #np.ravel(xymis[0]), np.ravel(xymis[1]))
        depth = deepcopy(depth)
        depth[xymis[0], xymis[1]] = guesses
        return depth

    def _filter_depth(self, depth):
        temp = self._fill_in_nans(depth)
        temp_denoised = \
            denoise_bilateral(temp, sigma_range=30, sigma_spatial=4.5)
        temp_denoised[np.isnan(depth)] = np.nan
        return temp_denoised

    def fuse(self, mu, filtering=False, measure_in_frustrum=False):
        '''
        mu is the truncation parameter. Default 0.03 as this is what PCL kinfu
        uses (measured in m).
        Variables ending in _f are full
            i.e. the same size as the full voxel grid
        Variables ending in _s are subsets
            i.e. typically of the same size as the number of voxels which ended
            up in the image
        Todo - should probably incorporate the numpy.ma module
        if filter==True, then each image is bilateral filtered before adding in
        '''
        # the kinfu accumulator, which keeps the rolling average
        accum = KinfuAccumulator(self.voxel_grid.V.shape)
        accum.vox_size = self.voxel_grid.vox_size
        accum.R = self.voxel_grid.R
        accum.inv_R = self.voxel_grid.inv_R
        accum.origin = self.voxel_grid.origin

        # another grid to store which voxels are visible, i.e on the surface
        visible_voxels = self.voxel_grid.blank_copy()
        visible_voxels.V = visible_voxels.V.astype(bool)

        # finally a third grid, which stores how many frustrums each voxel has
        # fallen into
        if measure_in_frustrum:
            self.in_frustrum = self.voxel_grid.blank_copy()
            self.in_frustrum.V = self.in_frustrum.V.astype(np.int16)

        for count, im in enumerate(self.video.frames):

            # print "Fusing frame number %d with name %s" % (count, im.frame_id)

            if filtering:
                depth = self._filter_depth(im.depth)
            else:
                depth = im.depth

            # work out which voxels are in front of or behind the depth image
            # and location in camera image of each voxel
            inside_image_f, uv_s, depth_to_voxels_s = self.project_voxels(im)
            observed_depths_s = depth[uv_s[:, 1], uv_s[:, 0]]

            # Distance between depth image and each voxel perpendicular to the
            # camera origin ray (this is *not* how kinfu does it: see ismar2011
            # eqn 6&7 for the real method, which operates along camera rays!)
            surface_to_voxel_dist_s = depth_to_voxels_s - observed_depths_s

            # finding indices of voxels which can be legitimately updated,
            # according to eqn 9 and the text after eqn 12
            valid_voxels_s = surface_to_voxel_dist_s <= mu

            # truncating the distance
            truncated_distance_s = -self.truncate(surface_to_voxel_dist_s, mu)

            # expanding the valid voxels to be a full grid
            valid_voxels_f = deepcopy(inside_image_f)
            valid_voxels_f[inside_image_f] = valid_voxels_s

            truncated_distance_ss = truncated_distance_s[valid_voxels_s]
            valid_voxels_ss = valid_voxels_s[valid_voxels_s]

            accum.update(
                valid_voxels_f, valid_voxels_ss, truncated_distance_ss)

            # now update the visible voxels - the array which says which voxels
            # are on the surface. I would like this to be automatically
            # extracted from the tsdf grid at the end but I failed to get this
            # to work properly (using the VisibleVoxels class below...) so
            # instead I will make it work here.
            voxels_visible_in_image_s = \
                np.abs(surface_to_voxel_dist_s) < np.sqrt(2) * self.voxel_grid.vox_size

            visible_voxels_f = inside_image_f
            visible_voxels_f[inside_image_f] = voxels_visible_in_image_s

            visible_voxels.set_indicated_voxels(visible_voxels_f, 1)

            if measure_in_frustrum:
                temp = inside_image_f.reshape(self.in_frustrum.V.shape)
                self.in_frustrum.V[temp] += 1

        return accum.get_current_tsdf(), visible_voxels


import scipy.io


class VisibleVoxels(object):
    '''
    This class uses a voxel grid to find the visible voxels! This is a new way
    of doing it...
    NOTE - it doesn't seem to really work!
    '''

    def __init__(self):
        raise Exception("This class doesn't seem to work"\
            " so I would not rely on it...")
        pass

    def set_voxel_grid(self, voxel_grid):
        self.voxel_grid = voxel_grid
        self.voxel_grid.V[np.isnan(self.voxel_grid.V)] = 0

    def axis_aligned_zero_crossings(self, V, axis):
        diff = np.diff(np.sign(V), axis=axis)

        padding = [[0, 0], [0, 0], [0, 0]]
        padding[axis] = [1, 0]
        diff1 = np.pad(diff, padding, 'edge')

        padding = [[0, 0], [0, 0], [0, 0]]
        padding[axis] = [0, 1]
        diff2 = np.pad(diff, padding, 'edge')

        return np.logical_or(diff1, diff2)

    def find_visible_voxels(self):
        '''
        finds all the zero-crossings in the voxel grid
        must ensure only use zero-crossings in the narrow-band
        '''
        # self.voxel_grid[np.isnan(self.voxel_grid)] =
        dx = self.axis_aligned_zero_crossings(self.voxel_grid.V, axis=0)
        dy = self.axis_aligned_zero_crossings(self.voxel_grid.V, axis=1)
        dz = self.axis_aligned_zero_crossings(self.voxel_grid.V, axis=2)

        temp = np.logical_or.reduce((dx, dy, dz))
        temp[self.voxel_grid.V > 0.09] = 0
        temp[self.voxel_grid.V < -0.09] = 0
        temp[np.isnan(self.voxel_grid.V)] = 0

        scipy.io.savemat('/tmp/temp.mat', {'temp': temp.astype(np.float32)})

        visible_grid = self.voxel_grid.blank_copy()
        visible_grid.V = temp
        return visible_grid, dx, dy, dz
