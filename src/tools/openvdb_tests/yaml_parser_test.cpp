#include <iostream>
#include <yaml-cpp/yaml.h>
#include <openvdb/openvdb.h>
#include <openvdb/tools/GridTransformer.h>
#include <openvdb/tools/Composite.h>
//#include <string>

using std::cout;
using std::cerr;
using std::endl;
std::string fullpath = "/Users/Michael/projects/shape_sharing/data/3D/basis_models/voxelised_vdb/";

// helper function to convert nodes containing R and T 
// components into openvdb transformation matrix format
openvdb::Mat4R extract_matrix(YAML::Node R, YAML::Node T)
{
	double zero = 0;
	double one = 1;
	openvdb::Mat4R trans( R[0][0].as<double>(), R[0][1].as<double>(), R[0][2].as<double>(), T[0].as<double>(),
					  	  R[1][0].as<double>(), R[1][1].as<double>(), R[1][2].as<double>(), T[1].as<double>(),
					  	  R[2][0].as<double>(), R[2][1].as<double>(), R[2][2].as<double>(), T[2].as<double>(),
					  	  zero, zero, zero, one);
	return trans;
}


int main()
{
	openvdb::initialize();
	YAML::Node transforms = YAML::LoadFile("test.yaml");

	// the final output grid...
	openvdb::FloatGrid::Ptr outputGrid = openvdb::FloatGrid::create();


	// loop over each object to be loaded in
	for (size_t i = 0; i < transforms.size(); ++i)
	{
		cerr << "Model number " << i << ": " << transforms[i]["name"] << endl;

		// extract a vector of openvdb transformations
		std::vector<openvdb::Mat4R > all_transforms;
		if (transforms[i]["transform"]["R"])
		{
			//cerr << 0 << ": " << transforms[i]["transform"] << endl;
			openvdb::Mat4R T = extract_matrix(transforms[i]["transform"]["R"], transforms[i]["transform"]["T"]);
			all_transforms.push_back(T);
		}
		else
			for (size_t j = 0; j < transforms[i]["transform"].size(); ++j)
			{
				//cerr << j << ": " << transforms[i]["transform"][j] << endl;
				openvdb::Mat4R T = extract_matrix(transforms[i]["transform"][j]["R"], transforms[i]["transform"][j]["T"]);
				all_transforms.push_back(T);
			}
		cerr << "There are " << all_transforms.size() << " transforms" << endl;	

		// load in the vdb voxel grid for this model
		std::string fullstring = fullpath + transforms[i]["name"].as<std::string>() + ".vdb";
		cerr << "Loading " << fullstring << endl;
		openvdb::io::File file(fullstring);
		file.open();
		openvdb::GridBase::Ptr baseGrid = file.readGrid("voxelgrid");
		file.close();

		// cast the baseGrid to a double grid
		openvdb::FloatGrid::Ptr grid = openvdb::gridPtrCast<openvdb::FloatGrid>(baseGrid);

		// go over the vector of the required transformations
		for (size_t j = 0; j < all_transforms.size(); ++j)
		{

			cout << "Transforming " << endl;
			const openvdb::Mat4R this_transform = all_transforms[j];
			cout << this_transform << endl;
			openvdb::FloatGrid::Ptr gridCopy = grid->deepCopy();
			openvdb::FloatGrid::Ptr targetGrid = openvdb::FloatGrid::create();

			//openvdb::math::Transform::Ptr linearTransform =
			  //  openvdb::math::Transform::createLinearTransform(this_transform);
			openvdb::tools::GridTransformer transformer(this_transform);

		    //targetGrid->setTransform(linearTransform);
   			//openvdb::tools::resampleToMatch<openvdb::tools::PointSampler>(*grid, *targetGrid);

			// Resample using nearest-neighbor interpolation.
			transformer.transformGrid<openvdb::tools::PointSampler, openvdb::FloatGrid>(
			    *gridCopy, *targetGrid);
			//break;

			// add into main grid (compositinbg modifies the frit grid and leaves the second empty)
			openvdb::tools::compSum(*outputGrid, *targetGrid);
			cerr << "Done transformation " << endl;
		}



	}


}