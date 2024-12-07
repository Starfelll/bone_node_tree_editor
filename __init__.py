bl_info = {
    "name": "Bone Node Tree Editor 🦴",
    #"description": "",
    "author": "Starfelll",
    "version": (1, 0),
    "blender": (3, 6, 0),
    #"location": "View3D > Add > Mesh",
    #"doc_url": "",
    #"tracker_url": "",
    "support": "COMMUNITY",
    "category": "Node",
}

import bpy
from bpy.types import NodeTree, Node, Operator, Context, Armature, Bone, Nodes
from bpy.props import BoolProperty
import mathutils
from datetime import datetime

_g_node_edit_lock = False
_g_bone_palette_to_index_map = {
    "DEFAULT": None,
    "THEME01": 0,
    "THEME02": 1,
    "THEME03": 2,
    "THEME04": 3,
    "THEME05": 4,
    "THEME06": 5,
    "THEME07": 6,
    "THEME08": 7,
    "THEME09": 8,
    "THEME10": 9,
    "THEME11": 10,
    "THEME12": 11,
    "THEME13": 12,
    "THEME14": 13,
    "THEME15": 14,
    "THEME16": 15,
    "THEME17": 16,
    "THEME18": 17,
    "THEME19": 17,
    "THEME20": 19,
    "CUSTOM": None
}

class BoneNodeTree(NodeTree):
    bl_idname = "bnte.BoneNodeTreeEditor"
    bl_label = "Bone node tree"
    bl_icon = "OUTLINER_OB_ARMATURE"
    #bl_icon = "NODETREE"

class BoneNode(Node):
    bl_idname = "bnte.BoneNode"
    bl_label = "Bone"
    bl_icon = "BONE_DATA"
    has_parent: BoolProperty(name="has_parent", default=False) # type: ignore

    def init(self, context):
        self.inputs.new("NodeSocketString", "parent")
        self.outputs.new("NodeSocketString", "Child Of")
        self.hide = True
        #self.mute = True

    def draw_label(self):
        return self.name
    
    @classmethod
    def poll(self, node_tree):
        global _g_node_edit_lock
        return _g_node_edit_lock
    
    def _set_bone_parent(self, parent: str | None) -> bool:
        context = bpy.context
        armature = _armature_of(context)
        if armature:
            if context.mode != "EDIT_ARMATURE":
                bone = armature.bones.get(self.name)
                node_tree = _bone_node_tree_of(context)

                for link in self.inputs["parent"].links:
                    node_tree.links.remove(link)
                if bone.parent:
                    node_parent = node_tree.nodes.get(bone.parent.name)
                    if node_parent:
                        node_tree.links.new(
                            node_parent.outputs["Child Of"], 
                            self.inputs["parent"]
                        )
                        return False
            else:
                bone = armature.edit_bones.get(self.name)
                bone_parent = None
                if parent:
                    bone_parent = armature.edit_bones.get(parent)
                if bone:
                    bone.parent = bone_parent
                    return True
        return False

    def insert_link(self, link: bpy.types.NodeLink):
        global _g_node_edit_lock
        if _g_node_edit_lock: return

        if bpy.context.mode != "EDIT_ARMATURE":
            #node_tree = _bone_node_tree_of(bpy.context)
            link.is_muted = True
            return

        if link.to_node != self: return

        if self._set_bone_parent(link.from_node.name):
            self.has_parent = True
            #print(f"跟新骨骼父级: {self.name} -> {link.from_node.name}")

    def update(self):
        global _g_node_edit_lock
        if _g_node_edit_lock: return

        # if self.has_parent == None:
        #     self._set_bone_parent(None)
        #     return

        if self.inputs["parent"].is_linked:
            link = self.inputs["parent"].links[0]
            if link and link.is_muted:
                self._set_bone_parent(None)
        elif self.has_parent:
            if self._set_bone_parent(None): pass
    

def _bone_node_tree_of(context: Context, name: str = "Bone node tree") -> NodeTree:
    node_groups = bpy.data.node_groups
    for node_group_name in node_groups:
        if node_group_name.name == name:
            return node_groups[name]

    return node_groups.new(name, BoneNodeTree.bl_idname)

def _armature_of(context: Context) -> None | Armature:
    if context.object != None and context.object.type == "ARMATURE":
        return context.object.data
    if context.pose_object != None and context.pose_object.type == "ARMATURE":
        return context.pose_object.data
    for obj in context.selected_objects:
        if obj.type == "ARMATURE":
            return obj.data
    return None

def _sync_bone_color_to_node(bone_color: bpy.types.BoneColor, node: Node):
    global _g_bone_palette_to_index_map
    if bone_color.is_custom:
        node.color = bone_color.custom.normal
        node.use_custom_color = True
    else:
        index = _g_bone_palette_to_index_map[bone_color.palette]
        theme = bpy.context.preferences.themes[0]
        if index != None:
            color_set = theme.bone_color_sets[index]
            if color_set:
                node.color = color_set.normal
                node.use_custom_color = True
        else:
            #node.color = mathutils.Color((0.2,0.2,0.2))
            #node.color = theme.view_3d.bone_pose
            node.use_custom_color = False


class OT_UpdateBoneNodeTree(Operator):
    bl_idname = "bnte.update_bone_node_tree"
    bl_label = "更新骨骼节点树"
    bl_options = {'REGISTER', 'UNDO'}
    only_visible = BoolProperty(name="only_visible", default=False) # type: ignore
    
    def arrange_nodes(self, root_bones: list[Bone], nodes: Nodes):
        subtree_height_map = {}
        default_node_height = 50
        
        def calculate_subtree_height(bone: Bone):
            result = 0
            if not bone.children:
                result = default_node_height
            else: 
                result = sum(calculate_subtree_height(c) for c in bone.children) # + (len(bone.children)-1) * default_height
            subtree_height_map[bone.name] = result
            return result
        
        def layout_node(bone: Bone, x, y):
            nodes.get(bone.name).location = (x,y)

            total_height2 = 0
            for child_bone in bone.children:
                total_height2 += subtree_height_map[child_bone.name]
            if total_height2 == 0:
                return
            
            start_y2 = -(total_height2) / 2
            start_y2 += y
            for child_bone in bone.children:
                subtree_height2 = subtree_height_map[child_bone.name]
                layout_node(child_bone, x + 150, start_y2 + (subtree_height2/2))
                start_y2 += subtree_height2
            pass

        total_height = 0
        for root_bone in root_bones:
            subtree_height = calculate_subtree_height(root_bone)
            total_height += subtree_height
        start_y = (total_height) / 2
        for root_bone in root_bones:
            subtree_height = subtree_height_map[root_bone.name]
            layout_node(root_bone, 0, start_y - (subtree_height/2))
            start_y -= subtree_height   

    def execute(self, context):
        node_tree = _bone_node_tree_of(context)
        nodes = node_tree.nodes

        armature = _armature_of(context)
        if armature is None:
            self.report({"INFO"}, "没有选中骨架")
            return {"CANCELLED"}

        #self.report({"INFO"}, "刷新骨骼列表")
        spacing_x = 10
        spacing_y = 10
        global _g_node_edit_lock
        _g_node_edit_lock = True
        bone_num = 0
        node_num = len(nodes)

        if context.mode == "EDIT_ARMATURE":
            bones = armature.edit_bones
        else:
            bones = armature.bones
        
        for bone in bones:
            bone_num += 1
            if bone_num <= node_num:
                node = nodes[bone_num-1]
            else:
                node = nodes.new(BoneNode.bl_idname)
            node.name = bone.name
            node.width = len(node.name) * 8
            node.select = bone.select
            node.has_parent = bone.parent != None
            _sync_bone_color_to_node(bone.color, node)
            if bones.active == bone:
                nodes.active = node
            
        if bone_num < node_num:
            unused_nodes = []
            for unused_node in range(bone_num, node_num):
                unused_nodes.append(nodes[unused_node])
            for unused_node in unused_nodes:
                nodes.remove(unused_node)
        

        root_bones = []
        for bone in bones:
            node = nodes.get(bone.name)
            if bone.parent:
                parentNode = nodes.get(bone.parent.name)
                if parentNode:
                    node_tree.links.new(
                        parentNode.outputs["Child Of"],
                        node.inputs["parent"]
                    )
            else:
                root_bones.append(bone)
            

        _g_node_edit_lock = False
        self.arrange_nodes(root_bones, nodes)

        #bpy.ops.node.view_selected()
        return {"FINISHED"}


class OT_SyncBoneNodeSelection(Operator):
    bl_idname = "bnte.sync_bone_node_selection"
    bl_label = "同步骨骼选择"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        node_tree = _bone_node_tree_of(context)
        nodes = node_tree.nodes
        for node in nodes: node.select = False

        if context.mode == "EDIT_ARMATURE":
            selected_bones = context.selected_editable_bones
            active_bone = context.active_bone
        elif context.mode == "POSE" or context.mode == "PAINT_WEIGHT":
            selected_bones = context.selected_pose_bones
            active_bone = context.active_pose_bone
        elif context.mode == "OBJECT":
            armature = _armature_of(context)
            if armature is None:
                self.report("INFO", "没有选中骨架")
                return {"CANCELLED"}
            active_bone = armature.bones.active
            if active_bone is None:
                active_bone = armature.edit_bones.active
            
            selected_bones = []
            for bone in armature.bones:
                if bone.select:
                    selected_bones.append(bone)
            if len(selected_bones) == 0:
                for bone in armature.edit_bones:
                    if bone.select:
                        selected_bones.append(bone)
        else:
            selected_bones = context.selected_bones
            active_bone = context.active_bone

        
        for bone in selected_bones:
            node = nodes.get(bone.name)
            if node: node.select = True
        
        if active_bone:
            nodes.active = nodes.get(active_bone.name)
        else:
            nodes.active = None

        return {"FINISHED"}


class _NodeTreeSnapshot():
    active = None
    active_select = None
    selected = {} #name, select
    handler = None
    region = "HEADER"
_old_nt = _NodeTreeSnapshot()

def _set_bone_select(bone, state: bool):
    bone.select = state
    bone.select_head = state
    bone.select_tail = state

def _is_in_bone_node_tree(context: Context):
    if context.space_data.tree_type == BoneNodeTree.bl_idname:
        return True
    return False

def _space_node_editor_draw():
    #print(f"_space_node_editor_draw: {datetime.now()}")
    is_dirty = False
    context = bpy.context

    if not _is_in_bone_node_tree(context):
        return
    
    if context.active_node and not context.active_node.hide:
        context.active_node.hide = True
    
    if _old_nt.active != context.active_node:
        is_dirty = True
    elif context.active_node != None and _old_nt.active != None:
        is_dirty = context.active_node.select != _old_nt.active_select

    if not is_dirty:
        for sel_node in context.selected_nodes:
            if sel_node.name not in _old_nt.selected:
                is_dirty = True
                break
    if not is_dirty:
        for old_sel_node_name in _old_nt.selected:
            if old_sel_node_name not in context.selected_nodes:
                is_dirty = True
                break

    if is_dirty:
        #print("Bone node tree is dirty")
        armature = _armature_of(context)
        if armature is not None:
            if context.mode == "EDIT_ARMATURE":
                bones = armature.edit_bones
            else:
                bones = armature.bones

            for bone in bones:
                _set_bone_select(bone, False)

            _old_nt.selected.clear()
            for node in context.selected_nodes:
                _old_nt.selected[node.name] = node.select
                bone = bones.get(node.name)
                if bone:
                    _set_bone_select(bone, node.select)
            
            if context.active_node:
                bone = bones.get(context.active_node.name)
                if bone and context.active_node.select: 
                    bones.active = bone
                    _set_bone_select(bone, True)
                    _old_nt.active_select = True
                    if context.mode == "PAINT_WEIGHT":
                        if context.object.vertex_groups.get(bone.name):
                            bpy.ops.object.vertex_group_set_active(group=bone.name)
                        else:
                            context.object.vertex_groups.active_index = -1
                else:
                    _old_nt.active_select = False
            else:
                bones.active = None
            _old_nt.active = context.active_node

    pass

def _draw_pie(this: bpy.types.Menu, context: Context):
    if _is_in_bone_node_tree(context):
        pie = this.layout.menu_pie()
        pie.operator(OT_SyncBoneNodeSelection.bl_idname, icon="UV_SYNC_SELECT")
        pie.operator(OT_UpdateBoneNodeTree.bl_idname, icon="OUTLINER_DATA_ARMATURE")

classes = [
    BoneNodeTree,
    BoneNode,
    OT_UpdateBoneNodeTree,
    OT_SyncBoneNodeSelection
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    pass
    global _old_nt
    _old_nt.handler = bpy.types.SpaceNodeEditor.draw_handler_add(
        _space_node_editor_draw, (), _old_nt.region, "POST_PIXEL"
    )
    bpy.types.NODE_MT_view_pie.append(_draw_pie)


def unregister():
    bpy.types.NODE_MT_view_pie.remove(_draw_pie)
    global _old_nt
    bpy.types.SpaceNodeEditor.draw_handler_remove(_old_nt.handler, _old_nt.region)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    pass