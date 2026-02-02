bl_info = {
    "name": "边属性转换工具",
    "author": "DeepSeek, Gemini 3 Pro, 3762822462",
    "version": (1, 0, 2),
    "blender": (5, 0, 1),
    "location": "3D Viewport > Sidebar > Edge Tools",
    "description": "转换选中边的锐边、缝合边和倒角权重属性",
    "category": "Mesh",
}

import bpy
import bmesh
from bpy.types import Operator, Panel
from bpy.props import BoolProperty, EnumProperty

# --- 核心辅助函数：兼容不同版本的倒角权重层获取 ---
def ensure_bevel_layer(bm):
    """
    安全地获取倒角权重层。
    兼容 Blender 3.x 和 Blender 4.x/5.x (通用属性系统)。
    """
    # 方法1: 尝试标准 API (旧版及部分新版兼容)
    try:
        return bm.edges.layers.bevel_weight.verify()
    except AttributeError:
        # 方法2: 如果标准属性不存在 (Blender 5.0+ 可能出现)，使用通用浮点层
        # 倒角权重在内部通常存储为名为 'bevel_weight_edge' 的浮点层
        layer = bm.edges.layers.float.get("bevel_weight_edge")
        if not layer:
            layer = bm.edges.layers.float.new("bevel_weight_edge")
        return layer

class MESH_OT_convert_edge_attributes(Operator):
    """转换边属性"""
    bl_idname = "mesh.convert_edge_attributes"
    bl_label = "转换边属性"
    bl_options = {'REGISTER', 'UNDO'}
    
    conversion_type: EnumProperty(
        name="转换类型",
        description="选择要执行的转换类型",
        items=[
            ('SHARP_TO_BEVEL', "锐边转倒角权重", "将锐边转换为倒角权重"),
            ('SHARP_TO_SEAM', "锐边转缝合边", "将锐边转换为缝合边"),
            ('SEAM_TO_SHARP', "缝合边转锐边", "将缝合边转换为锐边"),
            ('SEAM_TO_BEVEL', "缝合边转倒角权重", "将缝合边转换为倒角权重"),
        ],
        default='SHARP_TO_BEVEL'
    )
    
    clear_original: BoolProperty(
        name="清除原属性",
        description="转换后清除原有的属性",
        default=True
    )
    
    def execute(self, context):
        obj = context.active_object
        
        if obj is None or obj.type != 'MESH':
            self.report({'WARNING'}, "请选择一个网格物体")
            return {'CANCELLED'}
        
        # 确保在编辑模式
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        
        # 获取编辑模式的网格数据
        bm = bmesh.from_edit_mesh(obj.data)
        
        # --- 修复点：先确保倒角层存在，再获取边 ---
        # 如果先获取边再加层，会导致边的引用（指针）失效
        bw_layer = None
        if 'BEVEL' in self.conversion_type:
            bw_layer = ensure_bevel_layer(bm)
        
        # 获取选中的边 (必须在 ensure_bevel_layer 之后)
        selected_edges = [edge for edge in bm.edges if edge.select]
        
        if not selected_edges:
            self.report({'WARNING'}, "没有选中的边")
            return {'CANCELLED'}
        
        modified_count = 0
        
        for edge in selected_edges:
            if self.conversion_type == 'SHARP_TO_BEVEL':
                if edge.smooth == False:  # 锐边
                    edge[bw_layer] = 1.0
                    modified_count += 1
                    if self.clear_original:
                        edge.smooth = True
            
            elif self.conversion_type == 'SHARP_TO_SEAM':
                if edge.smooth == False:  # 锐边
                    edge.seam = True
                    modified_count += 1
                    if self.clear_original:
                        edge.smooth = True
            
            elif self.conversion_type == 'SEAM_TO_SHARP':
                if edge.seam:  # 缝合边
                    edge.smooth = False
                    modified_count += 1
                    if self.clear_original:
                        edge.seam = False
            
            elif self.conversion_type == 'SEAM_TO_BEVEL':
                if edge.seam:  # 缝合边
                    edge[bw_layer] = 1.0
                    modified_count += 1
                    if self.clear_original:
                        edge.seam = False
        
        # 更新网格
        bmesh.update_edit_mesh(obj.data)
        
        self.report({'INFO'}, f"成功转换 {modified_count} 条边")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


class MESH_OT_quick_convert_sharp_to_bevel(Operator):
    """快速转换：锐边→倒角权重"""
    bl_idname = "mesh.quick_convert_sharp_to_bevel"
    bl_label = "锐边→倒角权重"
    bl_description = "将选中的锐边转换为倒角权重"
    bl_options = {'REGISTER', 'UNDO'}
    
    clear_original: BoolProperty(
        name="清除锐边",
        description="转换后清除锐边属性",
        default=True
    )
    
    def execute(self, context):
        obj = context.active_object
        
        if obj is None or obj.type != 'MESH':
            self.report({'WARNING'}, "请选择一个网格物体")
            return {'CANCELLED'}
        
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        
        bm = bmesh.from_edit_mesh(obj.data)

        # --- 修复点：先创建层 ---
        bw_layer = ensure_bevel_layer(bm)

        # --- 后收集边 ---
        selected_edges = [edge for edge in bm.edges if edge.select]
        
        if not selected_edges:
            self.report({'WARNING'}, "没有选中的边")
            return {'CANCELLED'}
        
        modified_count = 0
        
        for edge in selected_edges:
            if edge.smooth == False:  # 锐边
                edge[bw_layer] = 1.0
                modified_count += 1
                if self.clear_original:
                    edge.smooth = True
        
        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"转换了 {modified_count} 条边")
        return {'FINISHED'}


class MESH_OT_quick_convert_sharp_to_seam(Operator):
    """快速转换：锐边→缝合边"""
    bl_idname = "mesh.quick_convert_sharp_to_seam"
    bl_label = "锐边→缝合边"
    bl_description = "将选中的锐边转换为缝合边"
    bl_options = {'REGISTER', 'UNDO'}
    
    clear_original: BoolProperty(
        name="清除锐边",
        description="转换后清除锐边属性",
        default=True
    )
    
    def execute(self, context):
        obj = context.active_object
        
        if obj is None or obj.type != 'MESH':
            self.report({'WARNING'}, "请选择一个网格物体")
            return {'CANCELLED'}
        
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        
        bm = bmesh.from_edit_mesh(obj.data)
        selected_edges = [edge for edge in bm.edges if edge.select]
        
        if not selected_edges:
            self.report({'WARNING'}, "没有选中的边")
            return {'CANCELLED'}
        
        modified_count = 0
        
        for edge in selected_edges:
            if edge.smooth == False:  # 锐边
                edge.seam = True
                modified_count += 1
                if self.clear_original:
                    edge.smooth = True
        
        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"转换了 {modified_count} 条边")
        return {'FINISHED'}


class MESH_OT_quick_convert_seam_to_sharp(Operator):
    """快速转换：缝合边→锐边"""
    bl_idname = "mesh.quick_convert_seam_to_sharp"
    bl_label = "缝合边→锐边"
    bl_description = "将选中的缝合边转换为锐边"
    bl_options = {'REGISTER', 'UNDO'}
    
    clear_original: BoolProperty(
        name="清除缝合边",
        description="转换后清除缝合边属性",
        default=True
    )
    
    def execute(self, context):
        obj = context.active_object
        
        if obj is None or obj.type != 'MESH':
            self.report({'WARNING'}, "请选择一个网格物体")
            return {'CANCELLED'}
        
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        
        bm = bmesh.from_edit_mesh(obj.data)
        selected_edges = [edge for edge in bm.edges if edge.select]
        
        if not selected_edges:
            self.report({'WARNING'}, "没有选中的边")
            return {'CANCELLED'}
        
        modified_count = 0
        
        for edge in selected_edges:
            if edge.seam:  # 缝合边
                edge.smooth = False
                modified_count += 1
                if self.clear_original:
                    edge.seam = False
        
        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"转换了 {modified_count} 条边")
        return {'FINISHED'}


class MESH_OT_quick_convert_seam_to_bevel(Operator):
    """快速转换：缝合边→倒角权重"""
    bl_idname = "mesh.quick_convert_seam_to_bevel"
    bl_label = "缝合边→倒角权重"
    bl_description = "将选中的缝合边转换为倒角权重"
    bl_options = {'REGISTER', 'UNDO'}
    
    clear_original: BoolProperty(
        name="清除缝合边",
        description="转换后清除缝合边属性",
        default=True
    )
    
    def execute(self, context):
        obj = context.active_object
        
        if obj is None or obj.type != 'MESH':
            self.report({'WARNING'}, "请选择一个网格物体")
            return {'CANCELLED'}
        
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        
        bm = bmesh.from_edit_mesh(obj.data)

        # --- 修复点：先创建层 ---
        bw_layer = ensure_bevel_layer(bm)

        # --- 后收集边 ---
        selected_edges = [edge for edge in bm.edges if edge.select]
        
        if not selected_edges:
            self.report({'WARNING'}, "没有选中的边")
            return {'CANCELLED'}
        
        modified_count = 0
        
        for edge in selected_edges:
            if edge.seam:  # 缝合边
                edge[bw_layer] = 1.0
                modified_count += 1
                if self.clear_original:
                    edge.seam = False
        
        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"转换了 {modified_count} 条边")
        return {'FINISHED'}


class VIEW3D_PT_edge_conversion_tools(Panel):
    """边属性转换工具面板"""
    bl_label = "边属性转换"
    bl_idname = "VIEW3D_PT_edge_conversion_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Edge Tools"
    bl_context = "mesh_edit"
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # 添加属性到场景以便面板访问
        if not hasattr(scene, "edge_clear_original"):
            scene.edge_clear_original = True
        
        box = layout.box()
        box.label(text="批量转换:", icon='MODIFIER')
        
        # 通用转换工具
        row = box.row(align=True)
        row.operator("mesh.convert_edge_attributes", text="通用转换", icon='SETTINGS')
        
        # 分隔线
        layout.separator()
        
        # 快速转换按钮
        box = layout.box()
        box.label(text="快速转换:", icon='RESTRICT_SELECT_OFF')
        
        # 第一行：锐边转换
        row = box.row(align=True)
        row.operator("mesh.quick_convert_sharp_to_bevel", text="锐边→倒角")
        row.operator("mesh.quick_convert_sharp_to_seam", text="锐边→缝合")
        
        # 第二行：缝合边转换
        row = box.row(align=True)
        row.operator("mesh.quick_convert_seam_to_sharp", text="缝合→锐边")
        row.operator("mesh.quick_convert_seam_to_bevel", text="缝合→倒角")
        
        # 分隔线
        layout.separator()
        
        # 选项
        box = layout.box()
        box.label(text="选项:", icon='PREFERENCES')
        
        # 清除原属性选项
        box.prop(scene, "edge_clear_original", text="清除原属性")
        
        # 说明文本
        box = layout.box()
        box.label(text="说明:", icon='INFO')
        box.label(text="1. 在编辑模式选择边")
        box.label(text="2. 点击相应转换按钮")
        box.label(text="3. 使用通用转换进行更多设置")


class VIEW3D_PT_edge_conversion_object_tools(Panel):
    """对象模式下的边属性转换工具面板"""
    bl_label = "边属性转换"
    bl_idname = "VIEW3D_PT_edge_conversion_object_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Edge Tools"
    bl_context = "objectmode"
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        box = layout.box()
        box.label(text="提示:", icon='INFO')
        box.label(text="请在编辑模式使用此工具")
        box.label(text="切换到编辑模式并选择边")
        
        # 添加进入编辑模式的快捷按钮
        row = box.row()
        row.operator("object.editmode_toggle", text="进入编辑模式", icon='EDITMODE_HLT')


# 存储属性到场景
def init_properties():
    bpy.types.Scene.edge_clear_original = BoolProperty(
        name="清除原属性",
        description="转换后清除原有的属性",
        default=True
    )


def clear_properties():
    try:
        del bpy.types.Scene.edge_clear_original
    except:
        pass


classes = (
    MESH_OT_convert_edge_attributes,
    MESH_OT_quick_convert_sharp_to_bevel,
    MESH_OT_quick_convert_sharp_to_seam,
    MESH_OT_quick_convert_seam_to_sharp,
    MESH_OT_quick_convert_seam_to_bevel,
    VIEW3D_PT_edge_conversion_tools,
    VIEW3D_PT_edge_conversion_object_tools,
)


def register():
    init_properties()
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    clear_properties()


if __name__ == "__main__":
    register()