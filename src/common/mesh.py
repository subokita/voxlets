import numpy as np
#https://github.com/dranjan/python-plyfile
from skimage.measure import marching_cubes


class Mesh(object):
    '''
    class for storing mesh data eg as read from a ply file
    '''

    def __init__(self):
        self.vertices = []
        self.faces = []
        self.norms = []


    def load_from_ply(self, filename):
        '''
        loads faces and vertices from a ply file
        '''
        from plyfile import PlyData, PlyElement
        f = open(filename, 'r')
        plydata = PlyData.read(f)
        f.close()
        self.vertices, self.faces = self._extract_plydata(plydata)

    def load_from_obj(self, filename):
        '''
        loads faces and vertices from a ply file
        '''
        with open(filename, 'r') as f:
            for l in f:
                split_line = l.strip().split(' ')
                if split_line[0] == '#':
                    continue
                elif split_line[0] == 'f':
                    self.faces.append([int(split_line[1]) - 1,
                                       int(split_line[2]) - 1,
                                       int(split_line[3]) - 1])
                elif split_line[0] == 'v':
                    self.vertices.append([float(split_line[1]),
                                          float(split_line[2]),
                                          float(split_line[3])])

        self.faces = np.array(self.faces)
        self.vertices = np.array(self.vertices)

    def write_to_obj(self, filename, labels=None):

        with open(filename, 'w') as f:

            f.write("# OBJ file \n")
            f.write("# generated by mfirman in a fit of rage\n")

            if labels != None:  # seems unpythonic but necessary when checking existance of numpy array...
                for vertex, label in zip(self.vertices, labels):
                    if label == 0:
                        f.write("usemtl grey\n")
                        f.write("v %.4f %.4f %.4f\n" %(vertex[0], vertex[1], vertex[2]))
                    elif label==1:
                        f.write("usemtl red\n")
                        f.write("v %.4f %.4f %.4f 0.7 0.1 0.1\n" %(vertex[0], vertex[1], vertex[2]))
            else:
                for vertex in self.vertices:
                    f.write("v %.4f %.4f %.4f\n" %(vertex[0], vertex[1], vertex[2]))
                    #f.write("v " + str(vertex[0]) + " " + str(vertex[1]) + " " + str(vertex[2]) + "\n")

            for face in self.faces:
                f.write("f %d %d %d\n" % (face[0]+1, face[1]+1, face[2]+1))

    def write_to_ply(self, filename, labels=None, colours=None):

        with open(filename, 'w') as f:

            f.write('ply\n')
            f.write('format ascii 1.0\n')
            f.write('comment author: Michael Firman\n')
            f.write('element vertex %d\n' % self.vertices.shape[0])
            f.write('property float x\n')
            f.write('property float y\n')
            f.write('property float z\n')
            if labels is not None or colours is not None:
                f.write('property uchar red\n')
                f.write('property uchar green\n')
                f.write('property uchar blue\n')
            f.write('element face %d\n' % self.faces.shape[0])
            f.write('property list uchar int vertex_indices\n')
            f.write('end_header\n')

            if labels is not None:
                print "Labels: ", labels.shape, labels.sum()
                for label, v in zip(labels, self.vertices):
                    if label == 0:
                        f.write("%f %f %f 128 128 128\n" % (v[0], v[1], v[2]))
                    elif label == 1:
                        f.write("%f %f %f 200 0 0\n" % (v[0], v[1], v[2]))
            elif colours is not None:
                assert colours.shape == self.vertices.shape
                print "Colours: ", colours.shape, colours.sum()
                for col, v in zip(colours, self.vertices):
                    f.write("%f %f %f %d %d %d\n" % (
                        v[0], v[1], v[2], col[0], col[1], col[2]))
            else:
                for v in self.vertices:
                    f.write("%f %f %f\n" % (v[0], v[1], v[2]))

            for face in self.faces:
                # we only have triangular faces
                f.write("3 %d %d %d\n" % (face[0], face[1], face[2]))

            f.write('element vertex %d\n' % self.vertices.shape[0])

    def read_from_obj(self, filename):
        '''
        not very good or robust - designed to work on simple files!
        '''
        self.faces = []
        self.vertices = []

        with open(filename, 'r') as f:

            for line in f:
                split_line = line.strip().split(' ')

                if split_line[0] == 'v':
                    self.vertices.append([float(v) for v in split_line[1:]])

                elif split_line[0] == 'f':
                    self.faces.append([int(f)-1 for f in split_line[1:]])

                elif split_line[0] == '#':
                    pass
                    #print "Comment... " + line

                #else:
                #    print "Unknown line: " + line

    def scale_mesh(self, scale):
        '''
        applys a scaling factor to the mesh vertices
        '''
        self.vertices *= scale

    def centre_mesh(self):
        '''
        centers the mesh such that the mean of the vertices is at (0, 0, 0)
        '''
        self.vertices = np.array(self.vertices)
        self.vertices -= np.mean(self.vertices, axis=0)

    def _extract_plydata(self, plydata):
        '''
        unpacks the structured array into standard np arrays
        '''
        vertices = plydata['vertex'].data
        np_vertex_data = vertices.view(np.float32).reshape(vertices.shape + (-1,))

        faces = np.zeros((plydata['face'].data.shape[0], 3), dtype=np.int32)
        for idx, t in enumerate(plydata['face'].data):
            faces[idx, :] = t[0]

        return np_vertex_data, faces

    def apply_transformation(self, trans):
        '''
        apply a 4x4 transformation matrix to the vertices
        '''
        n = self.vertices.shape[0]
        temp = np.concatenate((self.vertices, np.ones((n, 1))), axis=1).T
        temp_transformed = trans.dot(temp).T
        for idx in [0, 1, 2]:
            temp_transformed[:, idx] /= temp_transformed[:, 3]
        self.vertices = temp_transformed[:, :3]

    def _normalize_v3(self, arr):
        ''' Normalize a numpy array of 3 component vectors shape=(n,3) '''
        lens = np.sqrt(arr[:, 0]**2 + arr[:, 1]**2 + arr[:, 2]**2)
        arr[:, 0] /= lens
        arr[:, 1] /= lens
        arr[:, 2] /= lens
        return arr

    def compute_vertex_normals(self):
        '''
        https://sites.google.com/site/dlampetest/python/calculating-normals-of-a-triangle-mesh-using-numpy
        '''
        norms = np.zeros(self.vertices.shape, dtype=self.vertices.dtype)
        #Create an indexed view into the vertex array using the array of three indices for triangles
        tris = self.vertices[self.faces]
        #Calculate the normal for all the triangles, by taking the cross product of the vectors v1-v0, and v2-v0 in each triangle
        n = np.cross(tris[::, 1] - tris[::, 0], tris[::, 2] - tris[::, 0])
        # n is now an array of normals per triangle. The length of each normal is dependent the vertices,
        # we need to normalize these, so that our next step weights each normal equally.
        n = self._normalize_v3(n)
        # now we have a normalized array of normals, one per triangle, i.e., per triangle normals.
        # But instead of one per triangle (i.e., flat shading), we add to each vertex in that triangle,
        # the triangles' normal. Multiple triangles would then contribute to every vertex, so we need to normalize again afterwards.
        # The cool part, we can actually add the normals through an indexed view of our (zeroed) per vertex normal array
        norms[self.faces[:, 0]] += n
        norms[self.faces[:, 1]] += n
        norms[self.faces[:, 2]] += n
        norms = self._normalize_v3(norms)

        self.norms = norms

    def range(self):
        '''
        returns a 1 x 3 vector giving the size along each dimension
        '''
        return np.max(self.vertices, axis=0) - np.min(self.vertices, axis=0)

    def from_volume(self, voxel_grid, level=0):
        '''
        generates a mesh from a volume voxel_grid, using marching cubes
        voxel_grid should be a voxel grid object.
        This allows for the coordinates of the found mesh to be in world space.
        '''
        temp_verts, temp_faces = marching_cubes(voxel_grid.V, level)

        self.vertices = voxel_grid.idx_to_world(temp_verts)
        self.faces = temp_faces

    def remove_nan_vertices(self):
        '''
        Removes the nan vertices.
        Quite hard as must preserve the face indexing...

        Currently we just remove the faces which are attached to nan vertices
        We do not renumber face indices, so we cannot remove the nan vertices.
        '''

        verts_to_remove = np.any(np.isnan(self.vertices), axis=1)

        # generate a dictionary of verts to remove
        to_remove_dict = {vert: 1 for vert in np.where(verts_to_remove)[0]}

        faces_to_remove = np.zeros((self.faces.shape[0], ), dtype=np.bool)
        for idx, face in enumerate(self.faces):
            faces_to_remove[idx] = (face[0] in to_remove_dict or
                                    face[1] in to_remove_dict or
                                    face[2] in to_remove_dict)

        self.faces = self.faces[~faces_to_remove, :]

import h5py

class Camera(object):
    '''
    this is a projective (depth?) camera class.
    Should be able to do projection
    '''

    def __init__(self):
        self.K = []
        self.H = []

    def set_intrinsics(self, K):
        self.K = K
        self.inv_K = np.linalg.inv(K)


    def load_bigbird_matrices(self, folder, modelname, imagename):
        '''
        loads the extrinsics and intrinsics for a bigbird camera
        camera name is something like 'NP5'
        '''
        cameraname, angle = imagename.split('_')

        # loading the pose and calibration files
        calib = h5py.File(folder.replace('_cropped','') + modelname + "/calibration.h5", 'r')
        pose_path = folder.replace('_cropped','') + modelname + "/poses/NP5_" + angle + "_pose.h5"
        pose = h5py.File(pose_path, 'r')

        # extracting extrinsic and intrinsic matrices
        np5_to_this_camera = np.array(calib['H_' + cameraname + '_from_NP5'])
        mesh_to_np5 = np.linalg.inv(np.array(pose['H_table_from_reference_camera']))

        intrinsics = np.array(calib[cameraname +'_depth_K'])

        # applying to the camera
        self.set_extrinsics(np.linalg.inv(np5_to_this_camera.dot(mesh_to_np5)))
        self.set_intrinsics(intrinsics)


    def set_extrinsics(self, H):
        '''
        Extrinsics are the location of the camera relative to the world origin
        (This was fixed from being the incorrect way round in Jan 2015)
        '''
        self.H = H
        self.inv_H = np.linalg.inv(H)

    def adjust_intrinsic_scale(self, scale):
        '''
        changes the scaling, effectivly resixing the output image size
        '''
        self.K[0, 0] *= scale
        self.K[1, 1] *= scale
        self.K[0, 2] *= scale
        self.K[1, 2] *= scale
        self.inv_K = np.linalg.inv(self.K)

    def project_points(self, xyz):
        '''
        projects nx3 points xyz into the camera image
        returns their 2D projected location
        '''
        assert(xyz.shape[1] == 3)

        to_add = np.zeros((3, 1))
        full_K = np.concatenate((self.K, to_add), axis=1)
        full_mat = np.dot(full_K, self.inv_H)

        temp_trans = self._apply_homo_transformation(xyz, full_mat)

        temp_trans[:, 0] /= temp_trans[:, 2]
        temp_trans[:, 1] /= temp_trans[:, 2]

        return temp_trans  # [:, 0:2]

    def inv_project_points(self, uvd):
        '''
        throws u,v,d points in pixel coords (and depth)
        out into the real world, based on the transforms provided
        '''
        xyz_at_cam_loc = self.inv_project_points_cam_coords(uvd)

        # transforming points under the extrinsics
        return self._apply_normalised_homo_transform(xyz_at_cam_loc, self.H)

    def inv_project_points_cam_coords(self, uvd):
        '''
        as inv_project_points but doesn't do the homogeneous transformation
        '''
        assert(uvd.shape[1] == 3)
        n_points = uvd.shape[0]

        # creating the camera rays
        uv1 = np.hstack((uvd[:, :2], np.ones((n_points, 1))))
        camera_rays = np.dot(self.inv_K, uv1.T).T

        # forming the xyz points in the camera coordinates
        temp = uvd[:, 2][np.newaxis, :].T
        xyz_at_cam_loc = temp * camera_rays

        return xyz_at_cam_loc

    def inv_transform_normals(self, normals):
        '''
        Transforms normals under the camera extrinsics, such that they end up
        pointing the correct way in world space
        '''
        assert normals.shape[1] == 3
        R = np.linalg.inv(self.inv_H[:3, :3])
        #R = self.H[:3, :3]
        #print np.linalg.inv(self.H[:3, :3])
        #print np.linalg.inv(self.H)[:3, :3]
        return np.dot(R, normals.T).T

    def _apply_normalised_homo_transform(self, xyz, trans):
        '''
        applies homogeneous transform, and also does the normalising...
        '''
        temp = self._apply_homo_transformation(xyz, trans)
        return temp[:, :3] / temp[:, 3][:, np.newaxis]

    def _apply_transformation(self, xyz, trans):
        '''
        apply a 3x3 transformation matrix to the vertices
        '''
        to_add = np.zeros((3, 1))
        temp_trans = np.concatenate((trans, to_add), axis=1)
        return np.dot(temp_trans, xyz.T).T

    def _apply_homo_transformation(self, xyz, trans):
        '''
        apply a 4x4 transformation matrix to the vertices
        '''
        n = xyz.shape[0]
        temp = np.concatenate((xyz, np.ones((n, 1))), axis=1).T
        temp_transformed = trans.dot(temp).T
        return temp_transformed

    def estimate_focal_length(self):
        '''
        trys to guess the focal length from the intrinsics
        '''
        return self.K[0, 0]
