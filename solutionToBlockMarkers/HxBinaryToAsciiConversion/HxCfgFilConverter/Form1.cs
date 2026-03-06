using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Hamilton.Interop.HxReg;

namespace HxCfgFilConverter;

public class Form1 : Form
{
	private enum AllCheckBoxes
	{
		Checked,
		Unchecked,
		Enabled,
		Disabled,
		Shown,
		Hidden
	}

	private TreeNode treeViewRootDirectory;

	private TreeNode lastExploredNode;

	private DirectoryInfo lastSelectedDirectory;

	private string[] hamiltonRootDirectoryTokens;

	private string currentUserDesktopDirectory;

	private string diskWithHamiltonRootDirectory;

	private string lastSelectedDirectoryFullPath;

	private string lastSelectedRoot;

	private bool[] customFilters = new bool[9];

	private bool loadingCheckBoxes;

	private bool loadingHamiltonRootDirectory;

	private bool initializingForm;

	private bool restoringSelection;

	private bool accessDenied;

	private int indexOfUserDesktop;

	private List<string> extensionsToFilter = new List<string>();

	private List<string> selectedFiles = new List<string>();

	private List<int> driveType = new List<int>();

	private List<TreeNode> foundNodes = new List<TreeNode>();

	private IContainer components;

	private ImageList imageList1;

	private Button button1;

	private Button button2;

	private Button button3;

	private TextBox textBox1;

	private ComboBox comboBox1;

	private Panel panel1;

	private Panel panel2;

	private TreeView treeView1;

	private GroupBox groupBox1;

	private RadioButton radioButton1;

	private RadioButton radioButton3;

	private RadioButton radioButton2;

	private CheckBox checkBox1;

	private CheckBox checkBox2;

	private CheckBox checkBox3;

	private CheckBox checkBox4;

	private CheckBox checkBox5;

	private CheckBox checkBox6;

	private CheckBox checkBox7;

	private CheckBox checkBox8;

	private CheckBox checkBox9;

	private ImageList imageList2;

	private TextBox textBox2;

	private Panel panel3;

	private ListView listView1;

	private ColumnHeader columnHeader1;

	private ColumnHeader columnHeader2;

	private ColumnHeader columnHeader3;

	private Button button4;

	public Form1()
	{
		initializingForm = true;
		InitializeComponent();
		base.FormBorderStyle = FormBorderStyle.FixedSingle;
		PopulateComboBoxWithDrives();
		GetHamiltonBinDirectory();
		UpdateTreeViewWithHamiltonRootDirectory();
		treeView1.AfterSelect += treeView1_AfterSelect;
		treeView1.AfterExpand += treeView1_AfterExpand;
		treeView1.AfterCollapse += TreeView1_AfterCollapse;
		comboBox1.SelectedIndexChanged += comboBox1_SelectedIndexChanged;
		comboBox1.DrawItem += comboBox1_DrawItem;
		base.Shown += Form1_Shown;
		radioButton1.Select();
		initializingForm = false;
		textBox1.Text = "Ready";
	}

	private void PopulateComboBoxWithDrives()
	{
		DriveInfo[] drives = DriveInfo.GetDrives();
		currentUserDesktopDirectory = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
		string userName = Environment.UserName;
		DriveInfo[] array = drives;
		foreach (DriveInfo driveInfo in array)
		{
			if (driveInfo.DriveType.ToString() != "CDRom")
			{
				comboBox1.Items.Add(driveInfo.Name);
			}
			if (driveInfo.DriveType.ToString() == "Network")
			{
				driveType.Add(2);
			}
			else if (driveInfo.DriveType.ToString() == "Removable")
			{
				driveType.Add(3);
			}
			else
			{
				driveType.Add(0);
			}
			if (currentUserDesktopDirectory.StartsWith(driveInfo.Name))
			{
				comboBox1.Items.Add(userName + "'s Desktop");
				driveType.Add(4);
				indexOfUserDesktop = comboBox1.Items.IndexOf(userName + "'s Desktop");
			}
		}
	}

	private void GetHamiltonBinDirectory()
	{
		string binPath = ((HxRegistry)Activator.CreateInstance(Marshal.GetTypeFromCLSID(new Guid("70216FD1-A912-11D1-9925-0080296193E2")))).BinPath;
		hamiltonRootDirectoryTokens = binPath.Split('\\');
		_ = hamiltonRootDirectoryTokens.Length;
		diskWithHamiltonRootDirectory = hamiltonRootDirectoryTokens[0] + "\\";
	}

	private void UpdateTreeViewWithHamiltonRootDirectory()
	{
		string text = " ";
		TreeNode treeNode = null;
		treeView1.BeginUpdate();
		loadingHamiltonRootDirectory = true;
		if (treeViewRootDirectory != null)
		{
			treeView1.Nodes.Clear();
			treeViewRootDirectory.Remove();
		}
		if (initializingForm)
		{
			int selectedIndex = comboBox1.FindString(hamiltonRootDirectoryTokens[0]);
			comboBox1.SelectedIndex = selectedIndex;
		}
		lastSelectedRoot = comboBox1.SelectedItem.ToString();
		DirectoryInfo directoryInfo = new DirectoryInfo(comboBox1.SelectedItem.ToString());
		for (int i = 0; i < hamiltonRootDirectoryTokens.Length - 1; i++)
		{
			if (text == " ")
			{
				text.Remove(0);
				text = hamiltonRootDirectoryTokens[i];
				treeViewRootDirectory = new TreeNode(directoryInfo.Name);
				treeViewRootDirectory.Tag = directoryInfo;
				treeView1.Nodes.Add(treeViewRootDirectory);
				GetTwoLevelsOfDirectories(directoryInfo.GetDirectories(), treeViewRootDirectory);
				treeNode = treeViewRootDirectory;
			}
			else
			{
				text = text + "\\" + hamiltonRootDirectoryTokens[i];
				if (foundNodes != null)
				{
					foundNodes.Clear();
				}
				SearchNodesForTag(hamiltonRootDirectoryTokens[i], treeNode);
				foreach (TreeNode foundNode in foundNodes)
				{
					string fullPath = foundNode.FullPath;
					fullPath = fullPath.Replace("\\\\", "\\");
					if (text.ToLower() == fullPath.ToLower())
					{
						treeNode = foundNode;
					}
				}
				directoryInfo = (DirectoryInfo)treeNode.Tag;
				GetOneLevelOfDirectories(directoryInfo.GetDirectories(), treeNode);
			}
			treeView1.SelectedNode = treeNode;
			treeView1.SelectedNode.EnsureVisible();
		}
		treeView1.EndUpdate();
		loadingHamiltonRootDirectory = false;
		UpdateListView(directoryInfo);
	}

	private void UpdateTreeViewWithCurrentUserDesktopDirectory()
	{
		DirectoryInfo directoryInfo = new DirectoryInfo(currentUserDesktopDirectory);
		if (treeViewRootDirectory != null)
		{
			treeView1.Nodes.Clear();
			treeViewRootDirectory.Remove();
		}
		lastSelectedRoot = currentUserDesktopDirectory;
		if (directoryInfo.Exists)
		{
			treeViewRootDirectory = new TreeNode(directoryInfo.Name);
			treeViewRootDirectory.Tag = directoryInfo;
			treeView1.Nodes.Add(treeViewRootDirectory);
			treeViewRootDirectory.ImageIndex = 4;
			treeViewRootDirectory.SelectedImageIndex = 4;
			GetTwoLevelsOfDirectories(directoryInfo.GetDirectories(), treeViewRootDirectory);
		}
	}

	private void UpdateTreeViewWithNewRootDir(string rootPath)
	{
		DirectoryInfo directoryInfo = new DirectoryInfo(rootPath);
		if (treeViewRootDirectory != null)
		{
			treeView1.Nodes.Clear();
			treeViewRootDirectory.Remove();
		}
		lastSelectedRoot = comboBox1.SelectedItem.ToString();
		if (directoryInfo.Exists)
		{
			treeViewRootDirectory = new TreeNode(directoryInfo.Name);
			treeViewRootDirectory.Tag = directoryInfo;
			treeView1.Nodes.Add(treeViewRootDirectory);
			GetTwoLevelsOfDirectories(directoryInfo.GetDirectories(), treeViewRootDirectory);
		}
	}

	private void GetTwoLevelsOfDirectories(DirectoryInfo[] subDirsFirstLevel, TreeNode rootNode)
	{
		if (rootNode.Name.ToString() == "Explored")
		{
			return;
		}
		treeView1.BeginUpdate();
		foreach (DirectoryInfo directoryInfo in subDirsFirstLevel)
		{
			try
			{
				TreeNode treeNode = new TreeNode(directoryInfo.Name, 0, 0);
				treeNode.Tag = directoryInfo;
				DirectoryInfo[] directories = directoryInfo.GetDirectories();
				foreach (DirectoryInfo directoryInfo2 in directories)
				{
					TreeNode treeNode2 = new TreeNode(directoryInfo2.Name, 0, 0);
					treeNode2.Tag = directoryInfo2;
					treeNode.Nodes.Add(treeNode2);
				}
				rootNode.Nodes.Add(treeNode);
			}
			catch (Exception)
			{
			}
		}
		rootNode.Name = "Explored";
		rootNode.Expand();
		UpdateTreeNodeIcon(rootNode);
		treeView1.SelectedNode = rootNode;
		treeView1.EndUpdate();
	}

	private void GetOneLevelOfDirectories(DirectoryInfo[] subDirsFirstLevel, TreeNode rootNode)
	{
		string fullPath = rootNode.FullPath;
		fullPath = fullPath.Replace("\\\\", "\\");
		textBox2.Text = fullPath;
		textBox2.ScrollToCaret();
		if (rootNode.Name.ToString() == "Explored")
		{
			return;
		}
		int num = 0;
		treeView1.BeginUpdate();
		foreach (DirectoryInfo directoryInfo in subDirsFirstLevel)
		{
			try
			{
				DirectoryInfo[] directories = directoryInfo.GetDirectories();
				foreach (DirectoryInfo directoryInfo2 in directories)
				{
					TreeNode treeNode = new TreeNode(directoryInfo2.Name, 0, 0);
					treeNode.Tag = directoryInfo2;
					rootNode.Nodes[num].Nodes.Add(treeNode);
				}
			}
			catch (Exception)
			{
			}
			num++;
		}
		if (loadingHamiltonRootDirectory || initializingForm)
		{
			rootNode.Expand();
			UpdateTreeNodeIcon(rootNode);
		}
		rootNode.Name = "Explored";
		treeView1.EndUpdate();
	}

	private void UpdateListView(DirectoryInfo nodeDirInfo)
	{
		ListViewItem listViewItem = null;
		List<string> list = new List<string>();
		listView1.BeginUpdate();
		listView1.Items.Clear();
		if (radioButton1.Checked)
		{
			FileInfo[] files = nodeDirInfo.GetFiles();
			foreach (FileInfo fileInfo in files)
			{
				switch (fileInfo.Extension)
				{
				case ".cfg":
				case ".ctr":
				case ".med":
				case ".dck":
				case ".lay":
				case ".tpl":
				case ".tml":
				case ".stp":
				case ".rck":
				{
					listViewItem = new ListViewItem(fileInfo.Name, 1);
					ListViewItem.ListViewSubItem[] items = new ListViewItem.ListViewSubItem[2]
					{
						new ListViewItem.ListViewSubItem(listViewItem, fileInfo.Extension),
						new ListViewItem.ListViewSubItem(listViewItem, fileInfo.LastWriteTime.ToShortDateString() + " " + fileInfo.LastWriteTime.ToLongTimeString())
					};
					listViewItem.SubItems.AddRange(items);
					listView1.Items.Add(listViewItem);
					break;
				}
				}
			}
		}
		else if (radioButton2.Checked)
		{
			CreateCustomFilter();
			FileInfo[] files = nodeDirInfo.GetFiles();
			foreach (FileInfo fileInfo2 in files)
			{
				foreach (string item in extensionsToFilter)
				{
					if (fileInfo2.Extension == item)
					{
						listViewItem = new ListViewItem(fileInfo2.Name, 1);
						ListViewItem.ListViewSubItem[] items = new ListViewItem.ListViewSubItem[2]
						{
							new ListViewItem.ListViewSubItem(listViewItem, fileInfo2.Extension),
							new ListViewItem.ListViewSubItem(listViewItem, fileInfo2.LastWriteTime.ToShortDateString() + " " + fileInfo2.LastWriteTime.ToLongTimeString())
						};
						listViewItem.SubItems.AddRange(items);
						listView1.Items.Add(listViewItem);
					}
				}
			}
		}
		else
		{
			FileInfo[] files = nodeDirInfo.GetFiles();
			foreach (FileInfo fileInfo3 in files)
			{
				listViewItem = new ListViewItem(fileInfo3.Name, 1);
				ListViewItem.ListViewSubItem[] items = new ListViewItem.ListViewSubItem[2]
				{
					new ListViewItem.ListViewSubItem(listViewItem, fileInfo3.Extension),
					new ListViewItem.ListViewSubItem(listViewItem, fileInfo3.LastWriteTime.ToShortDateString() + " " + fileInfo3.LastWriteTime.ToLongTimeString())
				};
				listViewItem.SubItems.AddRange(items);
				listView1.Items.Add(listViewItem);
			}
		}
		restoringSelection = true;
		ListViewItem listViewItem2 = new ListViewItem();
		if (selectedFiles.Count > 0)
		{
			foreach (string selectedFile in selectedFiles)
			{
				listViewItem2 = listView1.FindItemWithText(selectedFile);
				if (listViewItem2 != null)
				{
					listViewItem2.Selected = true;
					listViewItem2 = null;
				}
				else
				{
					list.Add(selectedFile);
				}
			}
			foreach (string item2 in list)
			{
				selectedFiles.Remove(item2);
			}
		}
		restoringSelection = false;
		lastSelectedDirectory = nodeDirInfo;
		lastSelectedDirectoryFullPath = nodeDirInfo.FullName;
		listView1.EndUpdate();
	}

	private void LoadCustomFilters()
	{
		loadingCheckBoxes = true;
		checkBox1.Checked = customFilters[0];
		checkBox2.Checked = customFilters[1];
		checkBox3.Checked = customFilters[2];
		checkBox4.Checked = customFilters[3];
		checkBox5.Checked = customFilters[4];
		checkBox6.Checked = customFilters[5];
		checkBox7.Checked = customFilters[6];
		checkBox8.Checked = customFilters[7];
		checkBox9.Checked = customFilters[8];
		loadingCheckBoxes = false;
		UpdateListView(lastSelectedDirectory);
	}

	private void SaveCustomFilters()
	{
		customFilters[0] = checkBox1.Checked;
		customFilters[1] = checkBox2.Checked;
		customFilters[2] = checkBox3.Checked;
		customFilters[3] = checkBox4.Checked;
		customFilters[4] = checkBox5.Checked;
		customFilters[5] = checkBox6.Checked;
		customFilters[6] = checkBox7.Checked;
		customFilters[7] = checkBox8.Checked;
		customFilters[8] = checkBox9.Checked;
	}

	private void CreateCustomFilter()
	{
		extensionsToFilter.Clear();
		for (int i = 0; i < 9; i++)
		{
			if (customFilters[i])
			{
				switch (i)
				{
				case 0:
					extensionsToFilter.Add(".cfg");
					break;
				case 1:
					extensionsToFilter.Add(".ctr");
					break;
				case 2:
					extensionsToFilter.Add(".dck");
					break;
				case 3:
					extensionsToFilter.Add(".lay");
					break;
				case 4:
					extensionsToFilter.Add(".med");
					break;
				case 5:
					extensionsToFilter.Add(".rck");
					break;
				case 6:
					extensionsToFilter.Add(".stp");
					break;
				case 7:
					extensionsToFilter.Add(".tpl");
					break;
				case 8:
					extensionsToFilter.Add(".tml");
					break;
				}
			}
		}
	}

	private void ModifyCheckBoxes(AllCheckBoxes changeToState)
	{
		switch (changeToState)
		{
		case AllCheckBoxes.Checked:
			checkBox1.Checked = true;
			checkBox2.Checked = true;
			checkBox3.Checked = true;
			checkBox4.Checked = true;
			checkBox5.Checked = true;
			checkBox6.Checked = true;
			checkBox7.Checked = true;
			checkBox8.Checked = true;
			checkBox9.Checked = true;
			break;
		case AllCheckBoxes.Unchecked:
			checkBox1.Checked = false;
			checkBox2.Checked = false;
			checkBox3.Checked = false;
			checkBox4.Checked = false;
			checkBox5.Checked = false;
			checkBox6.Checked = false;
			checkBox7.Checked = false;
			checkBox8.Checked = false;
			checkBox9.Checked = false;
			break;
		case AllCheckBoxes.Enabled:
			checkBox1.Enabled = true;
			checkBox2.Enabled = true;
			checkBox3.Enabled = true;
			checkBox4.Enabled = true;
			checkBox5.Enabled = true;
			checkBox6.Enabled = true;
			checkBox7.Enabled = true;
			checkBox8.Enabled = true;
			checkBox9.Enabled = true;
			break;
		case AllCheckBoxes.Disabled:
			checkBox1.Enabled = false;
			checkBox2.Enabled = false;
			checkBox3.Enabled = false;
			checkBox4.Enabled = false;
			checkBox5.Enabled = false;
			checkBox6.Enabled = false;
			checkBox7.Enabled = false;
			checkBox8.Enabled = false;
			checkBox9.Enabled = false;
			break;
		case AllCheckBoxes.Shown:
			checkBox1.Show();
			checkBox2.Show();
			checkBox3.Show();
			checkBox4.Show();
			checkBox5.Show();
			checkBox6.Show();
			checkBox7.Show();
			checkBox8.Show();
			checkBox9.Show();
			break;
		case AllCheckBoxes.Hidden:
			checkBox1.Hide();
			checkBox2.Hide();
			checkBox3.Hide();
			checkBox4.Hide();
			checkBox5.Hide();
			checkBox6.Hide();
			checkBox7.Hide();
			checkBox8.Hide();
			checkBox9.Hide();
			break;
		}
	}

	private void SearchNodesForTag(string nodeTag, TreeNode startNode)
	{
		while (startNode != null)
		{
			if (startNode.Tag.ToString().ToLower() == nodeTag.ToLower())
			{
				foundNodes.Add(startNode);
			}
			if (startNode.Nodes.Count != 0)
			{
				SearchNodesForTag(nodeTag, startNode.Nodes[0]);
			}
			startNode = startNode.NextNode;
		}
	}

	private TreeNode SearchNodeByFullPath(string fullPath, TreeNode rootNode)
	{
		string text = fullPath;
		string text2 = text.Split(new string[1] { treeView1.PathSeparator }, StringSplitOptions.None).First();
		if (rootNode.Text.TrimEnd(treeView1.PathSeparator.ToCharArray()) != text2)
		{
			return null;
		}
		text = text.Remove(0, text2.Length);
		text = text.TrimStart('\\');
		if (text == "")
		{
			return rootNode;
		}
		foreach (TreeNode node in rootNode.Nodes)
		{
			if (node.Text.Length <= text.Length)
			{
				string text3 = text.Split(new string[1] { treeView1.PathSeparator }, StringSplitOptions.None).First();
				if (node.Text == text3)
				{
					treeView1.SelectedNode = node;
					return SearchNodeByFullPath(text, node);
				}
			}
		}
		return null;
	}

	private void UpdateTreeNodeIcon(TreeNode node)
	{
		if (node.ImageIndex != 4)
		{
			if (node.IsExpanded && node.IsSelected)
			{
				node.ImageIndex = 2;
				node.SelectedImageIndex = 2;
			}
			else if (node.IsExpanded && !node.IsSelected)
			{
				node.ImageIndex = 2;
				node.SelectedImageIndex = 2;
			}
			else if (!node.IsExpanded && node.IsSelected)
			{
				node.ImageIndex = 0;
				node.SelectedImageIndex = 0;
			}
			else
			{
				node.ImageIndex = 0;
				node.SelectedImageIndex = 0;
			}
		}
	}

	private void Form1_Shown(object sender, EventArgs e)
	{
		treeView1.Focus();
	}

	private void treeView1_AfterSelect(object sender, TreeViewEventArgs e)
	{
		TreeNode node = e.Node;
		accessDenied = false;
		treeView1.SuspendLayout();
		selectedFiles.Clear();
		try
		{
			DirectoryInfo directoryInfo = (DirectoryInfo)node.Tag;
			GetOneLevelOfDirectories(directoryInfo.GetDirectories(), node);
			UpdateListView(directoryInfo);
			lastExploredNode = node;
		}
		catch (UnauthorizedAccessException ex)
		{
			e.Node.Collapse();
			listView1.Items.Clear();
			MessageBox.Show(ex.Message, "Folder Access Error", MessageBoxButtons.OK, MessageBoxIcon.Hand);
			accessDenied = true;
		}
		catch (Exception ex2)
		{
			e.Node.Collapse();
			listView1.Items.Clear();
			MessageBox.Show(ex2.Message, ex2.Source);
		}
		treeView1.ResumeLayout();
	}

	private void treeView1_AfterExpand(object sender, TreeViewEventArgs e)
	{
		if (loadingHamiltonRootDirectory)
		{
			return;
		}
		TreeNode node = e.Node;
		accessDenied = false;
		UpdateTreeNodeIcon(node);
		try
		{
			DirectoryInfo directoryInfo = (DirectoryInfo)node.Tag;
			GetOneLevelOfDirectories(directoryInfo.GetDirectories(), node);
			UpdateListView(directoryInfo);
			lastExploredNode = node;
		}
		catch (Exception ex)
		{
			e.Node.Collapse();
			listView1.Items.Clear();
			MessageBox.Show(ex.Message, ex.Source, MessageBoxButtons.OK, MessageBoxIcon.Hand);
			accessDenied = true;
		}
	}

	private void TreeView1_AfterCollapse(object sender, TreeViewEventArgs e)
	{
		TreeNode node = e.Node;
		treeView1.SuspendLayout();
		UpdateTreeNodeIcon(node);
		treeView1.ResumeLayout();
	}

	private void comboBox1_SelectedIndexChanged(object sender, EventArgs e)
	{
		if (!initializingForm && lastSelectedRoot != comboBox1.SelectedItem.ToString())
		{
			if (comboBox1.SelectedItem.ToString() == diskWithHamiltonRootDirectory)
			{
				UpdateTreeViewWithHamiltonRootDirectory();
			}
			else if (comboBox1.SelectedIndex == indexOfUserDesktop)
			{
				UpdateTreeViewWithCurrentUserDesktopDirectory();
			}
			else
			{
				UpdateTreeViewWithNewRootDir(comboBox1.SelectedItem.ToString());
			}
		}
	}

	private void comboBox1_DrawItem(object sender, DrawItemEventArgs e)
	{
		e.DrawBackground();
		Image image = imageList2.Images[driveType[e.Index]];
		if ((e.State & DrawItemState.Selected) == DrawItemState.Selected)
		{
			e.Graphics.DrawImage(image, e.Bounds.X + 2, e.Bounds.Y - 1, 15, 15);
			e.Graphics.DrawString(comboBox1.Items[e.Index].ToString(), comboBox1.Font, Brushes.White, new RectangleF(e.Bounds.X + 19, e.Bounds.Y, e.Bounds.Width, e.Bounds.Height));
		}
		else
		{
			e.Graphics.DrawImage(image, e.Bounds.X + 2, e.Bounds.Y - 1, 15, 15);
			e.Graphics.DrawString(comboBox1.Items[e.Index].ToString(), comboBox1.Font, Brushes.Black, new RectangleF(e.Bounds.X + 19, e.Bounds.Y, e.Bounds.Width, e.Bounds.Height));
		}
		e.DrawFocusRectangle();
	}

	private void listView1_SelectedIndexChanged(object sender, EventArgs e)
	{
		if (restoringSelection)
		{
			return;
		}
		selectedFiles.Clear();
		foreach (ListViewItem selectedItem in listView1.SelectedItems)
		{
			selectedFiles.Add(selectedItem.Text);
		}
	}

	private void Form1_DragDrop(object sender, DragEventArgs e)
	{
		selectedFiles.Clear();
		radioButton3.Select();
		treeView1.CollapseAll();
		string[] array = (string[])e.Data.GetData(DataFormats.FileDrop);
		if (array == null || array.Length == 0)
		{
			return;
		}
		string directoryName = new FileInfo(array.First()).DirectoryName;
		TreeNode selectedNode = SearchNodeByFullPath(directoryName, treeViewRootDirectory);
		treeView1.SelectedNode = selectedNode;
		treeView1.Select();
		string[] array2 = array;
		for (int i = 0; i < array2.Length; i++)
		{
			string text = array2[i].Split('\\').Last();
			ListViewItem listViewItem = listView1.FindItemWithText(text);
			if (listViewItem != null)
			{
				selectedFiles.Add(listViewItem.Text);
				listViewItem.Selected = true;
			}
		}
		listView1.Select();
		int index = listView1.SelectedIndices[listView1.SelectedIndices.Count - 1];
		listView1.EnsureVisible(index);
		Activate();
	}

	private void Form1_DragEnter(object sender, DragEventArgs e)
	{
		if (!e.Data.GetDataPresent(DataFormats.FileDrop))
		{
			return;
		}
		string[] array = (string[])e.Data.GetData(DataFormats.FileDrop);
		for (int i = 0; i < array.Length; i++)
		{
			switch (new FileInfo(array[i]).Extension)
			{
			case ".cfg":
			case ".med":
			case ".dck":
			case ".rck":
			case ".lay":
			case ".tpl":
			case ".stp":
			case ".ctr":
			case ".tml":
			case ".crk":
				continue;
			}
			e.Effect = DragDropEffects.None;
			return;
		}
		e.Effect = DragDropEffects.Link;
	}

	private void radioButton1_CheckedChanged(object sender, EventArgs e)
	{
		selectedFiles.Clear();
		if (radioButton1.Checked)
		{
			ModifyCheckBoxes(AllCheckBoxes.Checked);
			ModifyCheckBoxes(AllCheckBoxes.Disabled);
			if (!initializingForm && !accessDenied)
			{
				UpdateListView(lastSelectedDirectory);
			}
		}
		else
		{
			ModifyCheckBoxes(AllCheckBoxes.Enabled);
		}
	}

	private void radioButton2_CheckedChanged(object sender, EventArgs e)
	{
		selectedFiles.Clear();
		if (radioButton2.Checked)
		{
			LoadCustomFilters();
			if (!initializingForm && !accessDenied)
			{
				UpdateListView(lastSelectedDirectory);
			}
		}
		else
		{
			SaveCustomFilters();
		}
	}

	private void radioButton3_CheckedChanged(object sender, EventArgs e)
	{
		selectedFiles.Clear();
		if (radioButton3.Checked)
		{
			ModifyCheckBoxes(AllCheckBoxes.Hidden);
			if (!initializingForm && !accessDenied)
			{
				UpdateListView(lastSelectedDirectory);
			}
		}
		else
		{
			ModifyCheckBoxes(AllCheckBoxes.Shown);
		}
	}

	private void checkBox1_CheckedChanged(object sender, EventArgs e)
	{
		if (radioButton2.Checked && !loadingCheckBoxes)
		{
			customFilters[0] = checkBox1.Checked;
			if (!initializingForm)
			{
				UpdateListView(lastSelectedDirectory);
			}
		}
	}

	private void checkBox2_CheckedChanged(object sender, EventArgs e)
	{
		if (radioButton2.Checked && !loadingCheckBoxes)
		{
			customFilters[1] = checkBox2.Checked;
			if (!initializingForm)
			{
				UpdateListView(lastSelectedDirectory);
			}
		}
	}

	private void checkBox3_CheckedChanged(object sender, EventArgs e)
	{
		if (radioButton2.Checked && !loadingCheckBoxes)
		{
			customFilters[2] = checkBox3.Checked;
			if (!initializingForm)
			{
				UpdateListView(lastSelectedDirectory);
			}
		}
	}

	private void checkBox4_CheckedChanged(object sender, EventArgs e)
	{
		if (radioButton2.Checked && !loadingCheckBoxes)
		{
			customFilters[3] = checkBox4.Checked;
			if (!initializingForm)
			{
				UpdateListView(lastSelectedDirectory);
			}
		}
	}

	private void checkBox5_CheckedChanged(object sender, EventArgs e)
	{
		if (radioButton2.Checked && !loadingCheckBoxes)
		{
			customFilters[4] = checkBox5.Checked;
			if (!initializingForm)
			{
				UpdateListView(lastSelectedDirectory);
			}
		}
	}

	private void checkBox6_CheckedChanged(object sender, EventArgs e)
	{
		if (radioButton2.Checked && !loadingCheckBoxes)
		{
			customFilters[5] = checkBox6.Checked;
			if (!initializingForm)
			{
				UpdateListView(lastSelectedDirectory);
			}
		}
	}

	private void checkBox7_CheckedChanged(object sender, EventArgs e)
	{
		if (radioButton2.Checked && !loadingCheckBoxes)
		{
			customFilters[6] = checkBox7.Checked;
			if (!initializingForm)
			{
				UpdateListView(lastSelectedDirectory);
			}
		}
	}

	private void checkBox8_CheckedChanged(object sender, EventArgs e)
	{
		if (radioButton2.Checked && !loadingCheckBoxes)
		{
			customFilters[7] = checkBox8.Checked;
			if (!initializingForm)
			{
				UpdateListView(lastSelectedDirectory);
			}
		}
	}

	private void checkBox9_CheckedChanged(object sender, EventArgs e)
	{
		if (radioButton2.Checked && !loadingCheckBoxes)
		{
			customFilters[8] = checkBox9.Checked;
			if (!initializingForm)
			{
				UpdateListView(lastSelectedDirectory);
			}
		}
	}

	private void button1_Click_1(object sender, EventArgs e)
	{
		listView1.Focus();
		if (selectedFiles.Count == 0)
		{
			textBox1.Text = "Conversion to Binary failed, no files are selected";
			return;
		}
		bool flag = false;
		Converter converter = new Converter();
		try
		{
			foreach (string selectedFile in selectedFiles)
			{
				string filename = Path.Combine(lastSelectedDirectoryFullPath, selectedFile);
				converter.LoadFile(filename);
				converter.SerializeFile(filename);
			}
		}
		catch (Exception ex)
		{
			flag = true;
			MessageBox.Show(ex.Message, "Conversion Error", MessageBoxButtons.OK, MessageBoxIcon.Hand);
		}
		UpdateListView(lastSelectedDirectory);
		if (flag)
		{
			textBox1.Text = "Conversion to Binary failed, error occurred during converion";
		}
		else if (selectedFiles.Count > 1)
		{
			textBox1.Text = "Selected files were successfully converted to Binary";
		}
		else
		{
			textBox1.Text = "Selected file was successfully converted to Binary";
		}
	}

	private void button2_Click_1(object sender, EventArgs e)
	{
		listView1.Focus();
		if (selectedFiles.Count == 0)
		{
			textBox1.Text = "Conversion to ASCII failed, no files are selected";
			return;
		}
		bool flag = false;
		Converter converter = new Converter();
		try
		{
			foreach (string selectedFile in selectedFiles)
			{
				string filename = Path.Combine(lastSelectedDirectoryFullPath, selectedFile);
				converter.LoadFile(filename);
				converter.StoreFile(filename);
			}
		}
		catch (Exception ex)
		{
			flag = true;
			MessageBox.Show(ex.Message, "Conversion Error", MessageBoxButtons.OK, MessageBoxIcon.Hand);
		}
		UpdateListView(lastSelectedDirectory);
		if (flag)
		{
			textBox1.Text = "Conversion to ASCII failed, error occurred during converion";
		}
		else if (selectedFiles.Count > 1)
		{
			textBox1.Text = "Selected files were successfully converted to ASCII";
		}
		else
		{
			textBox1.Text = "Selected file was successfully converted to ASCII";
		}
	}

	private void button3_Click(object sender, EventArgs e)
	{
		Application.Exit();
	}

	private void button4_Click(object sender, EventArgs e)
	{
		listView1.Focus();
		if (!initializingForm)
		{
			UpdateListView(lastSelectedDirectory);
		}
	}

	protected override void Dispose(bool disposing)
	{
		if (disposing && components != null)
		{
			components.Dispose();
		}
		base.Dispose(disposing);
	}

	private void InitializeComponent()
	{
		this.components = new System.ComponentModel.Container();
		System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(HxCfgFilConverter.Form1));
		this.imageList1 = new System.Windows.Forms.ImageList(this.components);
		this.button3 = new System.Windows.Forms.Button();
		this.textBox1 = new System.Windows.Forms.TextBox();
		this.button1 = new System.Windows.Forms.Button();
		this.button2 = new System.Windows.Forms.Button();
		this.comboBox1 = new System.Windows.Forms.ComboBox();
		this.panel1 = new System.Windows.Forms.Panel();
		this.groupBox1 = new System.Windows.Forms.GroupBox();
		this.checkBox9 = new System.Windows.Forms.CheckBox();
		this.checkBox8 = new System.Windows.Forms.CheckBox();
		this.checkBox7 = new System.Windows.Forms.CheckBox();
		this.checkBox6 = new System.Windows.Forms.CheckBox();
		this.checkBox5 = new System.Windows.Forms.CheckBox();
		this.checkBox4 = new System.Windows.Forms.CheckBox();
		this.checkBox3 = new System.Windows.Forms.CheckBox();
		this.checkBox2 = new System.Windows.Forms.CheckBox();
		this.checkBox1 = new System.Windows.Forms.CheckBox();
		this.radioButton2 = new System.Windows.Forms.RadioButton();
		this.radioButton3 = new System.Windows.Forms.RadioButton();
		this.radioButton1 = new System.Windows.Forms.RadioButton();
		this.treeView1 = new System.Windows.Forms.TreeView();
		this.panel2 = new System.Windows.Forms.Panel();
		this.listView1 = new System.Windows.Forms.ListView();
		this.columnHeader1 = new System.Windows.Forms.ColumnHeader();
		this.columnHeader2 = new System.Windows.Forms.ColumnHeader();
		this.columnHeader3 = new System.Windows.Forms.ColumnHeader();
		this.textBox2 = new System.Windows.Forms.TextBox();
		this.imageList2 = new System.Windows.Forms.ImageList(this.components);
		this.panel3 = new System.Windows.Forms.Panel();
		this.button4 = new System.Windows.Forms.Button();
		this.panel1.SuspendLayout();
		this.groupBox1.SuspendLayout();
		this.panel2.SuspendLayout();
		this.panel3.SuspendLayout();
		base.SuspendLayout();
		this.imageList1.ImageStream = (System.Windows.Forms.ImageListStreamer)resources.GetObject("imageList1.ImageStream");
		this.imageList1.TransparentColor = System.Drawing.Color.Transparent;
		this.imageList1.Images.SetKeyName(0, "folder.ico");
		this.imageList1.Images.SetKeyName(1, "Generic_Document.ico");
		this.imageList1.Images.SetKeyName(2, "folder_open.ico");
		this.imageList1.Images.SetKeyName(3, "WispRefresh.ico");
		this.imageList1.Images.SetKeyName(4, "Places-user-desktop-icon.png");
		this.button3.Location = new System.Drawing.Point(324, 487);
		this.button3.Name = "button3";
		this.button3.Size = new System.Drawing.Size(155, 26);
		this.button3.TabIndex = 3;
		this.button3.Text = "Close";
		this.button3.UseVisualStyleBackColor = true;
		this.button3.Click += new System.EventHandler(button3_Click);
		this.textBox1.BackColor = System.Drawing.SystemColors.Info;
		this.textBox1.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
		this.textBox1.Location = new System.Drawing.Point(0, 517);
		this.textBox1.Name = "textBox1";
		this.textBox1.ReadOnly = true;
		this.textBox1.Size = new System.Drawing.Size(479, 20);
		this.textBox1.TabIndex = 2;
		this.button1.Location = new System.Drawing.Point(162, 487);
		this.button1.Name = "button1";
		this.button1.Size = new System.Drawing.Size(155, 26);
		this.button1.TabIndex = 0;
		this.button1.Text = "Convert to Binary";
		this.button1.UseVisualStyleBackColor = true;
		this.button1.Click += new System.EventHandler(button1_Click_1);
		this.button2.Location = new System.Drawing.Point(0, 487);
		this.button2.Name = "button2";
		this.button2.Size = new System.Drawing.Size(155, 26);
		this.button2.TabIndex = 1;
		this.button2.Text = "Convert to ASCII";
		this.button2.UseVisualStyleBackColor = true;
		this.button2.Click += new System.EventHandler(button2_Click_1);
		this.comboBox1.Dock = System.Windows.Forms.DockStyle.Top;
		this.comboBox1.DrawMode = System.Windows.Forms.DrawMode.OwnerDrawFixed;
		this.comboBox1.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
		this.comboBox1.FormattingEnabled = true;
		this.comboBox1.Location = new System.Drawing.Point(0, 0);
		this.comboBox1.Name = "comboBox1";
		this.comboBox1.Size = new System.Drawing.Size(275, 21);
		this.comboBox1.TabIndex = 2;
		this.panel1.Controls.Add(this.groupBox1);
		this.panel1.Controls.Add(this.treeView1);
		this.panel1.Controls.Add(this.comboBox1);
		this.panel1.Location = new System.Drawing.Point(12, 13);
		this.panel1.Name = "panel1";
		this.panel1.Size = new System.Drawing.Size(275, 537);
		this.panel1.TabIndex = 4;
		this.groupBox1.Controls.Add(this.checkBox9);
		this.groupBox1.Controls.Add(this.checkBox8);
		this.groupBox1.Controls.Add(this.checkBox7);
		this.groupBox1.Controls.Add(this.checkBox6);
		this.groupBox1.Controls.Add(this.checkBox5);
		this.groupBox1.Controls.Add(this.checkBox4);
		this.groupBox1.Controls.Add(this.checkBox3);
		this.groupBox1.Controls.Add(this.checkBox2);
		this.groupBox1.Controls.Add(this.checkBox1);
		this.groupBox1.Controls.Add(this.radioButton2);
		this.groupBox1.Controls.Add(this.radioButton3);
		this.groupBox1.Controls.Add(this.radioButton1);
		this.groupBox1.Dock = System.Windows.Forms.DockStyle.Bottom;
		this.groupBox1.Location = new System.Drawing.Point(0, 452);
		this.groupBox1.Name = "groupBox1";
		this.groupBox1.Size = new System.Drawing.Size(275, 85);
		this.groupBox1.TabIndex = 4;
		this.groupBox1.TabStop = false;
		this.groupBox1.Text = "File Filters";
		this.checkBox9.AutoSize = true;
		this.checkBox9.Location = new System.Drawing.Point(219, 61);
		this.checkBox9.Name = "checkBox9";
		this.checkBox9.Size = new System.Drawing.Size(46, 17);
		this.checkBox9.TabIndex = 20;
		this.checkBox9.Text = "*.tml";
		this.checkBox9.UseVisualStyleBackColor = true;
		this.checkBox9.CheckedChanged += new System.EventHandler(checkBox9_CheckedChanged);
		this.checkBox8.AutoSize = true;
		this.checkBox8.Location = new System.Drawing.Point(219, 38);
		this.checkBox8.Name = "checkBox8";
		this.checkBox8.Size = new System.Drawing.Size(44, 17);
		this.checkBox8.TabIndex = 19;
		this.checkBox8.Text = "*.tpl";
		this.checkBox8.UseVisualStyleBackColor = true;
		this.checkBox8.CheckedChanged += new System.EventHandler(checkBox8_CheckedChanged);
		this.checkBox7.AutoSize = true;
		this.checkBox7.Location = new System.Drawing.Point(219, 15);
		this.checkBox7.Name = "checkBox7";
		this.checkBox7.Size = new System.Drawing.Size(47, 17);
		this.checkBox7.TabIndex = 18;
		this.checkBox7.Text = "*.stp";
		this.checkBox7.UseVisualStyleBackColor = true;
		this.checkBox7.CheckedChanged += new System.EventHandler(checkBox7_CheckedChanged);
		this.checkBox6.AutoSize = true;
		this.checkBox6.Location = new System.Drawing.Point(169, 61);
		this.checkBox6.Name = "checkBox6";
		this.checkBox6.Size = new System.Drawing.Size(48, 17);
		this.checkBox6.TabIndex = 17;
		this.checkBox6.Text = "*.rck";
		this.checkBox6.UseVisualStyleBackColor = true;
		this.checkBox6.CheckedChanged += new System.EventHandler(checkBox6_CheckedChanged);
		this.checkBox5.AutoSize = true;
		this.checkBox5.Location = new System.Drawing.Point(169, 38);
		this.checkBox5.Name = "checkBox5";
		this.checkBox5.Size = new System.Drawing.Size(53, 17);
		this.checkBox5.TabIndex = 16;
		this.checkBox5.Text = "*.med";
		this.checkBox5.UseVisualStyleBackColor = true;
		this.checkBox5.CheckedChanged += new System.EventHandler(checkBox5_CheckedChanged);
		this.checkBox4.AutoSize = true;
		this.checkBox4.Location = new System.Drawing.Point(169, 15);
		this.checkBox4.Name = "checkBox4";
		this.checkBox4.Size = new System.Drawing.Size(46, 17);
		this.checkBox4.TabIndex = 15;
		this.checkBox4.Text = "*.lay";
		this.checkBox4.UseVisualStyleBackColor = true;
		this.checkBox4.CheckedChanged += new System.EventHandler(checkBox4_CheckedChanged);
		this.checkBox3.AutoSize = true;
		this.checkBox3.Location = new System.Drawing.Point(118, 61);
		this.checkBox3.Name = "checkBox3";
		this.checkBox3.Size = new System.Drawing.Size(51, 17);
		this.checkBox3.TabIndex = 14;
		this.checkBox3.Text = "*.dck";
		this.checkBox3.UseVisualStyleBackColor = true;
		this.checkBox3.CheckedChanged += new System.EventHandler(checkBox3_CheckedChanged);
		this.checkBox2.AutoSize = true;
		this.checkBox2.Location = new System.Drawing.Point(118, 38);
		this.checkBox2.Name = "checkBox2";
		this.checkBox2.Size = new System.Drawing.Size(45, 17);
		this.checkBox2.TabIndex = 13;
		this.checkBox2.Text = "*.ctr";
		this.checkBox2.UseVisualStyleBackColor = true;
		this.checkBox2.CheckedChanged += new System.EventHandler(checkBox2_CheckedChanged);
		this.checkBox1.AutoSize = true;
		this.checkBox1.Location = new System.Drawing.Point(118, 15);
		this.checkBox1.Name = "checkBox1";
		this.checkBox1.Size = new System.Drawing.Size(48, 17);
		this.checkBox1.TabIndex = 12;
		this.checkBox1.Text = "*.cfg";
		this.checkBox1.UseVisualStyleBackColor = true;
		this.checkBox1.CheckedChanged += new System.EventHandler(checkBox1_CheckedChanged);
		this.radioButton2.AutoSize = true;
		this.radioButton2.Location = new System.Drawing.Point(6, 38);
		this.radioButton2.Name = "radioButton2";
		this.radioButton2.Size = new System.Drawing.Size(106, 17);
		this.radioButton2.TabIndex = 11;
		this.radioButton2.TabStop = true;
		this.radioButton2.Text = "Custom Std. Files";
		this.radioButton2.UseVisualStyleBackColor = true;
		this.radioButton2.CheckedChanged += new System.EventHandler(radioButton2_CheckedChanged);
		this.radioButton3.AutoSize = true;
		this.radioButton3.Location = new System.Drawing.Point(6, 61);
		this.radioButton3.Name = "radioButton3";
		this.radioButton3.Size = new System.Drawing.Size(60, 17);
		this.radioButton3.TabIndex = 10;
		this.radioButton3.TabStop = true;
		this.radioButton3.Text = "All Files";
		this.radioButton3.UseVisualStyleBackColor = true;
		this.radioButton3.CheckedChanged += new System.EventHandler(radioButton3_CheckedChanged);
		this.radioButton1.AutoSize = true;
		this.radioButton1.Location = new System.Drawing.Point(6, 15);
		this.radioButton1.Name = "radioButton1";
		this.radioButton1.Size = new System.Drawing.Size(106, 17);
		this.radioButton1.TabIndex = 0;
		this.radioButton1.TabStop = true;
		this.radioButton1.Text = "All Standard Files";
		this.radioButton1.UseVisualStyleBackColor = true;
		this.radioButton1.CheckedChanged += new System.EventHandler(radioButton1_CheckedChanged);
		this.treeView1.HideSelection = false;
		this.treeView1.ImageIndex = 0;
		this.treeView1.ImageList = this.imageList1;
		this.treeView1.Location = new System.Drawing.Point(0, 27);
		this.treeView1.Name = "treeView1";
		this.treeView1.SelectedImageIndex = 0;
		this.treeView1.Size = new System.Drawing.Size(275, 419);
		this.treeView1.TabIndex = 0;
		this.panel2.Controls.Add(this.listView1);
		this.panel2.Controls.Add(this.button1);
		this.panel2.Controls.Add(this.button2);
		this.panel2.Controls.Add(this.textBox1);
		this.panel2.Controls.Add(this.button3);
		this.panel2.Location = new System.Drawing.Point(293, 13);
		this.panel2.Name = "panel2";
		this.panel2.Size = new System.Drawing.Size(479, 537);
		this.panel2.TabIndex = 6;
		this.listView1.Columns.AddRange(new System.Windows.Forms.ColumnHeader[3] { this.columnHeader1, this.columnHeader2, this.columnHeader3 });
		this.listView1.FullRowSelect = true;
		this.listView1.HideSelection = false;
		this.listView1.Location = new System.Drawing.Point(0, 27);
		this.listView1.Name = "listView1";
		this.listView1.Size = new System.Drawing.Size(479, 454);
		this.listView1.SmallImageList = this.imageList1;
		this.listView1.TabIndex = 0;
		this.listView1.UseCompatibleStateImageBehavior = false;
		this.listView1.View = System.Windows.Forms.View.Details;
		this.listView1.SelectedIndexChanged += new System.EventHandler(listView1_SelectedIndexChanged);
		this.columnHeader1.Text = "Name";
		this.columnHeader1.Width = 273;
		this.columnHeader2.Text = "Type";
		this.columnHeader2.Width = 50;
		this.columnHeader3.Text = "Last Modified";
		this.columnHeader3.Width = 135;
		this.textBox2.BackColor = System.Drawing.SystemColors.Info;
		this.textBox2.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
		this.textBox2.Font = new System.Drawing.Font("Microsoft Sans Serif", 8.25f);
		this.textBox2.Location = new System.Drawing.Point(0, 1);
		this.textBox2.Name = "textBox2";
		this.textBox2.ReadOnly = true;
		this.textBox2.Size = new System.Drawing.Size(455, 20);
		this.textBox2.TabIndex = 4;
		this.imageList2.ImageStream = (System.Windows.Forms.ImageListStreamer)resources.GetObject("imageList2.ImageStream");
		this.imageList2.TransparentColor = System.Drawing.Color.Transparent;
		this.imageList2.Images.SetKeyName(0, "Hard_Drive.png");
		this.imageList2.Images.SetKeyName(1, "CD_Drive.png");
		this.imageList2.Images.SetKeyName(2, "Network_Drive.png");
		this.imageList2.Images.SetKeyName(3, "EmptyDrive.ico");
		this.imageList2.Images.SetKeyName(4, "Places-user-desktop-icon.png");
		this.panel3.BackColor = System.Drawing.SystemColors.Info;
		this.panel3.Controls.Add(this.button4);
		this.panel3.Controls.Add(this.textBox2);
		this.panel3.Location = new System.Drawing.Point(293, 13);
		this.panel3.Name = "panel3";
		this.panel3.Size = new System.Drawing.Size(479, 21);
		this.panel3.TabIndex = 5;
		this.button4.BackColor = System.Drawing.SystemColors.Info;
		this.button4.FlatAppearance.MouseOverBackColor = System.Drawing.Color.White;
		this.button4.FlatStyle = System.Windows.Forms.FlatStyle.Popup;
		this.button4.ImageIndex = 3;
		this.button4.ImageList = this.imageList1;
		this.button4.Location = new System.Drawing.Point(454, 1);
		this.button4.Name = "button4";
		this.button4.Size = new System.Drawing.Size(25, 20);
		this.button4.TabIndex = 4;
		this.button4.UseVisualStyleBackColor = true;
		this.button4.Click += new System.EventHandler(button4_Click);
		this.AllowDrop = true;
		base.AutoScaleDimensions = new System.Drawing.SizeF(6f, 13f);
		base.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
		this.AutoSize = true;
		base.ClientSize = new System.Drawing.Size(784, 562);
		base.Controls.Add(this.panel3);
		base.Controls.Add(this.panel2);
		base.Controls.Add(this.panel1);
		base.Icon = (System.Drawing.Icon)resources.GetObject("$this.Icon");
		base.MaximizeBox = false;
		base.Name = "Form1";
		this.Text = "HxCfgFilConverter";
		base.DragDrop += new System.Windows.Forms.DragEventHandler(Form1_DragDrop);
		base.DragEnter += new System.Windows.Forms.DragEventHandler(Form1_DragEnter);
		this.panel1.ResumeLayout(false);
		this.groupBox1.ResumeLayout(false);
		this.groupBox1.PerformLayout();
		this.panel2.ResumeLayout(false);
		this.panel2.PerformLayout();
		this.panel3.ResumeLayout(false);
		this.panel3.PerformLayout();
		base.ResumeLayout(false);
	}
}
