import yaml
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def configure(context, *args, **kwargs):
    ip = LaunchConfiguration("ip")
    namespace = LaunchConfiguration("namespace")
    base_frame = LaunchConfiguration("base_frame")

    cfg_path = LaunchConfiguration("config").perform(context)
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    trackers = cfg["controller_manager"]["ros__parameters"]["trackers"]
    tracker_names_str = ",".join([t["name"] for t in trackers])
    tracker_sroms_str = ",".join([t["srom"] for t in trackers])

    xacro_cmd = Command(
        [
            PathJoinSubstitution([FindExecutable(name="xacro")]),
            " ",
            PathJoinSubstitution(
                [
                    FindPackageShare("ndi_description"),
                    "urdf",
                    "polaris.urdf.xacro",
                ]
            ),
            " name:=ndi",
            f" tracker_names:='{tracker_names_str}'",
            f" tracker_sroms:='{tracker_sroms_str}'",  # xacro will handle the substitution
            " ip:=",
            ip,
            " base_frame:=",
            base_frame,
        ]
    )
    description_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="screen",
        parameters=[{"robot_description": ParameterValue(xacro_cmd, value_type=str)}],
        namespace=namespace,
    )

    control_node = Node(
        package="controller_manager",
        executable="ros2_control_node",
        namespace=namespace,
        parameters=[cfg_path],
        output="screen",
    )

    spawners = [
        Node(
            package="controller_manager",
            executable="spawner",
            namespace=namespace,
            arguments=[
                f"{t['name']}_pose_broadcaster",
                "--param-file",
                PathJoinSubstitution(
                    [
                        FindPackageShare("ndi_bringup"),
                        "config",
                        "pose_broadcaster_type.yaml",
                    ]
                ),
                [
                    f"--controller-ros-args=-p pose_name:={t['name']} -p frame_id:=",
                    base_frame,
                ],  # concat string and substitution into a single string
            ],
            output="screen",
        )
        for t in trackers
    ]

    return [description_node, control_node, *spawners]


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "ndi_ip",
                default_value="0.0.0.0",
                description="IP address of the NDI optical tracking system",
            ),
            DeclareLaunchArgument(
                "namespace",
                default_value="ndi",
                description="ROS 2 namespace",
            ),
            DeclareLaunchArgument(
                "base_frame",
                default_value="polaris_base",
                description="Base frame name",
            ),
            # The YAML file should have the following structure:
            # controller_manager:
            #   ros__parameters:
            #     trackers:
            #       - name: <tracker_name>
            #         srom: <srom_file_path>
            DeclareLaunchArgument(
                "config",
                default_value=PathJoinSubstitution(
                    [FindPackageShare("ndi_bringup"), "config", "ndi_trackers.yaml"]
                ),
                description="Path to tracker YAML",
            ),
            OpaqueFunction(function=configure),
        ]
    )
