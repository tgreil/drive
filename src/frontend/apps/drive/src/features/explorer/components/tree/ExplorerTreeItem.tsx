import { Item, TreeItem } from "@/features/drivers/types";
import folderIcon from "@/assets/tree/folder.svg";
import {
  NodeRendererProps,
  TreeDataItem,
  TreeViewItem,
  TreeViewNodeTypeEnum,
} from "@gouvfr-lasuite/ui-kit";
import { DroppableNodeTree } from "./DroppableNodeTree";
import { NavigationEventType, useExplorer } from "../ExplorerContext";

type ExplorerTreeItemProps = NodeRendererProps<TreeDataItem<TreeItem>>;

export const ExplorerTreeItem = ({ ...props }: ExplorerTreeItemProps) => {
  const { onNavigate } = useExplorer();
  const item = props.node.data.value as TreeItem;

  return (
    <DroppableNodeTree id={props.node.id} item={item} nodeTree={props}>
      <TreeViewItem
        {...props}
        onClick={() => {
          onNavigate({
            type: NavigationEventType.ITEM,
            item: item as Item,
          });
        }}
      >
        <div className="explorer__tree__item">
          <img src={folderIcon.src} alt="folder" />
          {item.nodeType === TreeViewNodeTypeEnum.NODE && (
            <span className="explorer__tree__item__title">{item.title}</span>
          )}
        </div>
      </TreeViewItem>
    </DroppableNodeTree>
  );
};
